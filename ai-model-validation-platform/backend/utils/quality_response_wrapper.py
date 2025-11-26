"""
Quality-Aware API Response Wrapper

Automatically enhances API responses with quality information, warnings,
and recommendations without requiring manual additions in every endpoint.

Features:
- Automatic quality warning injection for sessions with degraded timing
- Validation statistics in all relevant responses
- Smart recommendations based on quality metrics
- Zero-touch integration via response models
- Performance-optimized database queries

Usage:
    from utils.quality_response_wrapper import enhance_session_response

    @app.get("/api/test-sessions/{session_id}")
    async def get_session(session_id: str, db: Session = Depends(get_db)):
        session = db.query(TestSession).filter_by(id=session_id).first()
        # Automatically enhance response with quality info
        return enhance_session_response(session, db)

Author: Backend Integration Agent
Date: 2025-11-19
"""

import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

logger = logging.getLogger(__name__)


class QualityInfo:
    """Quality information container"""

    def __init__(self, session_id: str, db: Session):
        """
        Initialize quality info

        Args:
            session_id: Test session ID
            db: Database session
        """
        self.session_id = session_id
        self.db = db
        self._cached_info = None

    def get_info(self) -> Dict[str, Any]:
        """
        Get complete quality information for a session

        Returns:
            Dictionary with quality warnings, stats, and recommendations
        """
        if self._cached_info is not None:
            return self._cached_info

        from models import TestSession, DetectionEvent

        try:
            # Get session
            session = self.db.query(TestSession).filter(
                TestSession.id == self.session_id
            ).first()

            if not session:
                return self._empty_quality_info()

            # Get detection statistics
            detection_stats = self.db.query(
                func.count(DetectionEvent.id).label('total'),
                func.sum(DetectionEvent.usable_for_validation.cast(type_=int)).label('usable'),
                func.sum(DetectionEvent.timing_degraded.cast(type_=int)).label('degraded')
            ).filter(
                DetectionEvent.test_session_id == self.session_id
            ).first()

            total_detections = detection_stats.total or 0
            usable_detections = detection_stats.usable or 0
            degraded_detections = detection_stats.degraded or 0

            # Calculate percentages
            usable_pct = (usable_detections / total_detections * 100) if total_detections > 0 else 100
            degraded_pct = (degraded_detections / total_detections * 100) if total_detections > 0 else 0

            # Build quality info
            quality_info = {
                'timing_degraded': session.timing_degraded,
                'timing_verified': session.timing_verified,
                'validation_statistics': {
                    'total_detections': total_detections,
                    'usable_detections': usable_detections,
                    'degraded_detections': degraded_detections,
                    'usable_percentage': round(usable_pct, 1),
                    'degraded_percentage': round(degraded_pct, 1)
                },
                'warnings': self._generate_warnings(session, usable_pct, degraded_pct),
                'recommendations': self._generate_recommendations(session, usable_pct, degraded_pct)
            }

            self._cached_info = quality_info
            return quality_info

        except Exception as e:
            logger.error(f"Error getting quality info for session {self.session_id}: {e}")
            return self._empty_quality_info()

    def _empty_quality_info(self) -> Dict[str, Any]:
        """Return empty quality info structure"""
        return {
            'timing_degraded': False,
            'timing_verified': False,
            'validation_statistics': {
                'total_detections': 0,
                'usable_detections': 0,
                'degraded_detections': 0,
                'usable_percentage': 0.0,
                'degraded_percentage': 0.0
            },
            'warnings': [],
            'recommendations': []
        }

    def _generate_warnings(
        self,
        session,
        usable_pct: float,
        degraded_pct: float
    ) -> List[Dict[str, str]]:
        """Generate quality warnings based on session state"""
        warnings = []

        # Timing degradation warning
        if session.timing_degraded:
            warnings.append({
                'level': 'warning',
                'message': 'Session uses degraded timing (wall clock instead of precision timing)',
                'impact': 'Latency measurements may be less accurate'
            })

        # Unverified timing warning
        if not session.timing_verified:
            warnings.append({
                'level': 'info',
                'message': 'Timing has not been verified against database',
                'impact': 'Data integrity not confirmed'
            })

        # Low usable detection percentage
        if usable_pct < 50:
            warnings.append({
                'level': 'error',
                'message': f'Only {usable_pct:.1f}% of detections are usable for validation',
                'impact': 'Results may not be statistically significant'
            })
        elif usable_pct < 75:
            warnings.append({
                'level': 'warning',
                'message': f'{usable_pct:.1f}% of detections are usable for validation',
                'impact': 'Consider investigating detection quality issues'
            })

        # High degraded detection percentage
        if degraded_pct > 50:
            warnings.append({
                'level': 'error',
                'message': f'{degraded_pct:.1f}% of detections have degraded timing',
                'impact': 'Timing accuracy severely compromised'
            })
        elif degraded_pct > 25:
            warnings.append({
                'level': 'warning',
                'message': f'{degraded_pct:.1f}% of detections have degraded timing',
                'impact': 'Some timing measurements may be inaccurate'
            })

        return warnings

    def _generate_recommendations(
        self,
        session,
        usable_pct: float,
        degraded_pct: float
    ) -> List[str]:
        """Generate recommendations based on quality metrics"""
        recommendations = []

        if session.timing_degraded:
            recommendations.append(
                "Enable precision timing for future tests to improve accuracy"
            )

        if not session.timing_verified:
            recommendations.append(
                "Verify timing data against database to ensure integrity"
            )

        if usable_pct < 75:
            recommendations.append(
                "Investigate and fix detection timing issues to improve data quality"
            )

        if degraded_pct > 25:
            recommendations.append(
                "Review timing configuration to reduce degraded detections"
            )

        if len(recommendations) == 0:
            recommendations.append(
                "Quality metrics are good - no immediate action required"
            )

        return recommendations


def enhance_session_response(
    session_data: Dict[str, Any],
    session_id: str,
    db: Session
) -> Dict[str, Any]:
    """
    Enhance session response with quality information

    Args:
        session_data: Original session response data
        session_id: Test session ID
        db: Database session

    Returns:
        Enhanced response with quality info
    """
    try:
        quality_info = QualityInfo(session_id, db).get_info()

        # Add quality info to response
        enhanced = {
            **session_data,
            'quality': quality_info
        }

        return enhanced

    except Exception as e:
        logger.error(f"Error enhancing session response: {e}")
        # Return original data if enhancement fails
        return session_data


def enhance_results_response(
    results_data: Dict[str, Any],
    session_id: str,
    db: Session
) -> Dict[str, Any]:
    """
    Enhance test results response with quality warnings

    Args:
        results_data: Original results response data
        session_id: Test session ID
        db: Database session

    Returns:
        Enhanced response with quality warnings in results
    """
    try:
        quality_info = QualityInfo(session_id, db).get_info()

        # Add warnings to results
        enhanced = {
            **results_data,
            'data_quality': {
                'warnings': quality_info['warnings'],
                'validation_stats': quality_info['validation_statistics'],
                'recommendations': quality_info['recommendations']
            }
        }

        return enhanced

    except Exception as e:
        logger.error(f"Error enhancing results response: {e}")
        return results_data


def get_quality_summary(session_id: str, db: Session) -> Dict[str, Any]:
    """
    Get quality summary for a session (standalone endpoint)

    Args:
        session_id: Test session ID
        db: Database session

    Returns:
        Quality summary with warnings and recommendations
    """
    return QualityInfo(session_id, db).get_info()
