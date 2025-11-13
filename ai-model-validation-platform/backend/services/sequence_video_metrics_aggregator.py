"""
Sequence Video Metrics Aggregator Service

MISSION: Agent #32 - Implement per-video metrics calculation for multi-video sessions
QUEEN'S PROTOCOL: Exact variable alignment with SequenceVideoResult model

This service calculates per-video metrics from DetectionEvent table and updates
SequenceVideoResult records. Solves the CRITICAL BLOCKER where per-video metrics
show NULL values in API responses.

VARIABLE ALIGNMENT (Queen's Protocol):
- session_id (str) - Test session identifier
- video_id (str) - Video identifier
- tp (int) - True Positives count
- fp (int) - False Positives count
- fn (int) - False Negatives count
- precision (float) - tp / (tp + fp)
- recall (float) - tp / (tp + fn)
- f1 (float) - harmonic mean of precision and recall
- actual_latency_ms (float) - from DetectionEvent
- match_status (str) - from DetectionEvent ('TP', 'FP', 'FN')
- avg_latency_ms (float) - average latency
- median_latency_ms (float) - median latency
- p50_latency_ms (float) - 50th percentile
- p95_latency_ms (float) - 95th percentile
- p99_latency_ms (float) - 99th percentile
"""

import logging
import statistics
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from models import DetectionEvent, SequenceVideoResult, VideoTestSequence

logger = logging.getLogger(__name__)

# CRITICAL: Use numpy for percentile calculations if available, fallback to statistics
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    logger.warning("numpy not available - using statistics module for percentiles")


class SequenceVideoMetricsAggregator:
    """
    Calculate per-video metrics from DetectionEvent table for multi-video sessions.

    CRITICAL FIX: This service fills NULL metrics in SequenceVideoResult records
    by querying DetectionEvent table and calculating:
    - Match status counts (TP, FP, FN)
    - Precision, Recall, F1 scores
    - Latency statistics (avg, median, p50, p95, p99)

    QUEEN'S PROTOCOL: All variable names match SequenceVideoResult model exactly.
    """

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    async def aggregate_video_metrics(
        self,
        db: Session,
        session_id: str,
        video_id: str
    ) -> Dict[str, Any]:
        """
        Calculate per-video metrics from DetectionEvent table.

        Args:
            db: Database session
            session_id: Test session ID
            video_id: Video ID to calculate metrics for

        Returns:
            Dict containing calculated metrics:
            {
                'tp': int,
                'fp': int,
                'fn': int,
                'precision': float,
                'recall': float,
                'f1': float,
                'avg_latency_ms': float,
                'median_latency_ms': float,
                'p50_latency_ms': float,
                'p95_latency_ms': float,
                'p99_latency_ms': float,
                'min_latency_ms': float,
                'max_latency_ms': float,
                'total_detections': int,
                'passed_detections': int,
                'failed_detections': int
            }
        """
        try:
            self.logger.info(
                f"Calculating metrics for video {video_id} in session {session_id}"
            )

            # Query all detections for this video in this session
            detections: List[DetectionEvent] = db.query(DetectionEvent).filter(
                DetectionEvent.test_session_id == session_id,
                DetectionEvent.video_id == video_id
            ).all()

            if not detections:
                self.logger.warning(
                    f"No detections found for video {video_id} in session {session_id}"
                )
                return self._empty_metrics()

            self.logger.info(
                f"Found {len(detections)} detections for video {video_id}"
            )

            # Count by match_status (Queen's Protocol variable names)
            tp = sum(1 for d in detections if d.match_status == 'TP')
            fp = sum(1 for d in detections if d.match_status == 'FP')
            fn = sum(1 for d in detections if d.match_status == 'FN')

            self.logger.info(
                f"Match status counts - TP: {tp}, FP: {fp}, FN: {fn}"
            )

            # Calculate precision, recall, f1 with safe division (Queen's Protocol)
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = (
                2 * (precision * recall) / (precision + recall)
                if (precision + recall) > 0
                else 0.0
            )

            self.logger.info(
                f"Metrics - Precision: {precision:.3f}, Recall: {recall:.3f}, "
                f"F1: {f1:.3f}"
            )

            # Calculate latency stats from TP detections only
            # CRITICAL: Exclude latencies >= 10000ms (invalid/timeout values)
            valid_latencies = [
                d.actual_latency_ms
                for d in detections
                if d.match_status == 'TP'
                and d.actual_latency_ms is not None
                and d.actual_latency_ms < 10000.0
            ]

            if not valid_latencies:
                self.logger.warning(
                    f"No valid latencies found for video {video_id} - "
                    "latency stats will be 0.0"
                )
                latency_stats = {
                    'avg_latency_ms': 0.0,
                    'median_latency_ms': 0.0,
                    'p50_latency_ms': 0.0,
                    'p95_latency_ms': 0.0,
                    'p99_latency_ms': 0.0,
                    'min_latency_ms': 0.0,
                    'max_latency_ms': 0.0
                }
            else:
                self.logger.info(
                    f"Calculating latency stats from {len(valid_latencies)} "
                    "valid latency values"
                )

                # Calculate basic stats with statistics module
                avg_latency_ms = statistics.mean(valid_latencies)
                median_latency_ms = statistics.median(valid_latencies)
                min_latency_ms = min(valid_latencies)
                max_latency_ms = max(valid_latencies)

                # Calculate percentiles (Queen's Protocol variable names)
                if NUMPY_AVAILABLE:
                    p50_latency_ms = float(np.percentile(valid_latencies, 50))
                    p95_latency_ms = float(np.percentile(valid_latencies, 95))
                    p99_latency_ms = float(np.percentile(valid_latencies, 99))
                else:
                    # Fallback to statistics.quantiles for Python 3.8+
                    sorted_latencies = sorted(valid_latencies)
                    n = len(sorted_latencies)
                    p50_latency_ms = sorted_latencies[int(n * 0.50)]
                    p95_latency_ms = sorted_latencies[int(n * 0.95)]
                    p99_latency_ms = sorted_latencies[int(n * 0.99)]

                latency_stats = {
                    'avg_latency_ms': avg_latency_ms,
                    'median_latency_ms': median_latency_ms,
                    'p50_latency_ms': p50_latency_ms,
                    'p95_latency_ms': p95_latency_ms,
                    'p99_latency_ms': p99_latency_ms,
                    'min_latency_ms': min_latency_ms,
                    'max_latency_ms': max_latency_ms
                }

                self.logger.info(
                    f"Latency stats - Avg: {avg_latency_ms:.2f}ms, "
                    f"Median: {median_latency_ms:.2f}ms, "
                    f"P95: {p95_latency_ms:.2f}ms, "
                    f"P99: {p99_latency_ms:.2f}ms"
                )

            # Count passed/failed detections for SequenceVideoResult
            passed_detections = tp  # TP detections are passed
            failed_detections = fp + fn  # FP and FN are failed
            total_detections = len(detections)

            # Assemble complete metrics dict (Queen's Protocol)
            metrics = {
                'tp': tp,
                'fp': fp,
                'fn': fn,
                'precision': precision,
                'recall': recall,
                'f1': f1,
                'total_detections': total_detections,
                'passed_detections': passed_detections,
                'failed_detections': failed_detections,
                **latency_stats
            }

            # Update SequenceVideoResult with calculated metrics
            updated = await self._update_sequence_video_result(
                db, session_id, video_id, metrics
            )

            if updated:
                self.logger.info(
                    f"✅ Successfully updated SequenceVideoResult for video {video_id}"
                )
            else:
                self.logger.warning(
                    f"⚠️ Could not find SequenceVideoResult to update for video {video_id}"
                )

            return metrics

        except Exception as e:
            self.logger.error(
                f"Failed to calculate metrics for video {video_id} in session "
                f"{session_id}: {e}",
                exc_info=True
            )
            return self._empty_metrics()

    async def _update_sequence_video_result(
        self,
        db: Session,
        session_id: str,
        video_id: str,
        metrics: Dict[str, Any]
    ) -> bool:
        """
        Update SequenceVideoResult with calculated metrics.

        Args:
            db: Database session
            session_id: Test session ID
            video_id: Video ID
            metrics: Calculated metrics dict

        Returns:
            bool: True if updated successfully, False otherwise
        """
        try:
            # Find VideoTestSequence for this session
            video_sequence = db.query(VideoTestSequence).filter(
                VideoTestSequence.test_session_id == session_id
            ).first()

            if not video_sequence:
                self.logger.error(
                    f"No VideoTestSequence found for session {session_id}"
                )
                return False

            # Find SequenceVideoResult for this video
            sequence_video_result = db.query(SequenceVideoResult).filter(
                SequenceVideoResult.video_sequence_id == video_sequence.id,
                SequenceVideoResult.video_id == video_id
            ).first()

            if not sequence_video_result:
                self.logger.error(
                    f"No SequenceVideoResult found for video {video_id} in "
                    f"sequence {video_sequence.id}"
                )
                return False

            # Update metrics fields (Queen's Protocol alignment)
            sequence_video_result.passed_detections = metrics['passed_detections']
            sequence_video_result.failed_detections = metrics['failed_detections']
            sequence_video_result.actual_detection_count = metrics['total_detections']

            sequence_video_result.avg_latency_ms = metrics['avg_latency_ms']
            sequence_video_result.min_latency_ms = metrics.get('min_latency_ms')
            sequence_video_result.max_latency_ms = metrics.get('max_latency_ms')

            # Calculate pass rate
            if metrics['total_detections'] > 0:
                pass_rate_percent = (
                    metrics['passed_detections'] / metrics['total_detections']
                ) * 100.0
                sequence_video_result.pass_rate_percent = pass_rate_percent
            else:
                sequence_video_result.pass_rate_percent = 0.0

            # Determine validation result based on pass rate and metrics
            if metrics['f1'] >= 0.8 and pass_rate_percent >= 80.0:
                sequence_video_result.validation_result = 'Pass'
            elif metrics['total_detections'] == 0:
                sequence_video_result.validation_result = 'Error'
            else:
                sequence_video_result.validation_result = 'Fail'

            db.commit()

            self.logger.info(
                f"Updated SequenceVideoResult {sequence_video_result.id} - "
                f"Pass Rate: {pass_rate_percent:.1f}%, "
                f"Result: {sequence_video_result.validation_result}"
            )

            return True

        except Exception as e:
            self.logger.error(
                f"Failed to update SequenceVideoResult for video {video_id}: {e}",
                exc_info=True
            )
            db.rollback()
            return False

    def _empty_metrics(self) -> Dict[str, Any]:
        """
        Return empty metrics dict when no detections found.

        Returns:
            Dict with all metrics set to 0
        """
        return {
            'tp': 0,
            'fp': 0,
            'fn': 0,
            'precision': 0.0,
            'recall': 0.0,
            'f1': 0.0,
            'avg_latency_ms': 0.0,
            'median_latency_ms': 0.0,
            'p50_latency_ms': 0.0,
            'p95_latency_ms': 0.0,
            'p99_latency_ms': 0.0,
            'min_latency_ms': 0.0,
            'max_latency_ms': 0.0,
            'total_detections': 0,
            'passed_detections': 0,
            'failed_detections': 0
        }


# Global service instance
sequence_video_metrics_aggregator = SequenceVideoMetricsAggregator()


# Convenience function for external use
async def aggregate_video_metrics(
    db: Session,
    session_id: str,
    video_id: str
) -> Dict[str, Any]:
    """
    Calculate and update per-video metrics.

    Args:
        db: Database session
        session_id: Test session ID
        video_id: Video ID

    Returns:
        Dict of calculated metrics
    """
    return await sequence_video_metrics_aggregator.aggregate_video_metrics(
        db, session_id, video_id
    )
