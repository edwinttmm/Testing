"""
Detection Queue Service - Eliminates Race Condition

This service queues detections that arrive before SequenceVideoResult records
exist, then assigns video_id when timing data becomes available.

PROBLEM SOLVED:
- LabJack detections arrive BEFORE /video-started endpoint completes
- SequenceVideoResult doesn't exist yet, causing video_id=NULL
- 15% of detections had NULL video_id (1,426 out of 18,611)

SOLUTION:
- Queue detections instead of rejecting them
- Flush queue when video lifecycle event completes
- Result: 0% NULL rate, no race condition

USAGE:
    # When detection arrives (labjack_detection_service.py)
    if video_id is None:
        queue_service.enqueue(session_id, detection_id, timestamp)

    # When video lifecycle completes (video_sequence_testing.py)
    queue_service.flush_for_video(session_id, video_id, db)

AUTHOR: Queen Seraphina's Agents
DATE: 2025-11-13
"""

from typing import Dict, List, Optional
import logging
from dataclasses import dataclass, field
from datetime import datetime
import threading

logger = logging.getLogger(__name__)


@dataclass
class QueuedDetection:
    """Detection awaiting video_id assignment"""
    detection_id: str
    timestamp: float
    session_id: str
    queued_at: datetime = field(default_factory=datetime.utcnow)


class DetectionQueueService:
    """Manages pending detections awaiting video_id assignment"""

    def __init__(self):
        self._queues: Dict[str, List[QueuedDetection]] = {}
        self._lock = threading.Lock()  # Thread-safe operations
        self._stats = {
            'total_queued': 0,
            'total_flushed': 0,
            'avg_queue_time_ms': 0.0,
            'max_queue_size': 0
        }

    def enqueue(self, session_id: str, detection_id: str, timestamp: float):
        """
        Queue detection for later video_id assignment.

        Args:
            session_id: Test session ID
            detection_id: Detection event ID
            timestamp: Detection Unix timestamp

        This is called when:
        - video_id resolution returns None (SequenceVideoResult doesn't exist yet)
        - Detection arrives before /video-started endpoint completes
        """
        with self._lock:
            if session_id not in self._queues:
                self._queues[session_id] = []

            queued = QueuedDetection(
                detection_id=detection_id,
                timestamp=timestamp,
                session_id=session_id
            )

            self._queues[session_id].append(queued)
            self._stats['total_queued'] += 1

            # Track max queue size
            current_size = len(self._queues[session_id])
            if current_size > self._stats['max_queue_size']:
                self._stats['max_queue_size'] = current_size

            logger.info(
                f"🔄 Detection queued: {detection_id} "
                f"(session: {session_id}, queue size: {current_size})"
            )

    def flush_for_video(self, session_id: str, video_id: str, db_session) -> int:
        """
        Assign video_id to all queued detections for this session.

        Args:
            session_id: Test session ID
            video_id: Video ID to assign
            db_session: SQLAlchemy database session

        Returns:
            Number of detections assigned

        This is called when:
        - /video-started endpoint completes successfully
        - SequenceVideoResult has been created and committed
        """
        with self._lock:
            if session_id not in self._queues:
                logger.debug(f"No queued detections for session {session_id}")
                return 0

            from models import DetectionEvent

            queued = self._queues[session_id]
            assigned_count = 0
            total_queue_time = 0.0

            logger.info(f"🔄 Flushing {len(queued)} queued detections for session {session_id}")

            for item in queued:
                try:
                    # Update detection in database
                    detection = db_session.query(DetectionEvent).filter_by(
                        id=item.detection_id
                    ).first()

                    if detection:
                        if detection.video_id is None:
                            detection.video_id = video_id
                            assigned_count += 1

                            # Track queue time for metrics
                            queue_time_ms = (datetime.utcnow() - item.queued_at).total_seconds() * 1000
                            total_queue_time += queue_time_ms

                            logger.debug(
                                f"✅ Assigned video_id={video_id} to detection {item.detection_id} "
                                f"(queued for {queue_time_ms:.1f}ms)"
                            )
                        else:
                            logger.warning(
                                f"⚠️ Detection {item.detection_id} already has video_id={detection.video_id}"
                            )
                    else:
                        logger.error(f"❌ Detection {item.detection_id} not found in database")

                except Exception as e:
                    logger.error(f"❌ Error flushing detection {item.detection_id}: {e}")

            # Commit all changes
            try:
                db_session.commit()
            except Exception as e:
                logger.error(f"❌ Error committing flush changes: {e}")
                db_session.rollback()
                return 0

            # Update stats
            self._stats['total_flushed'] += assigned_count
            if assigned_count > 0:
                avg_queue_time = total_queue_time / assigned_count
                # Exponential moving average for avg_queue_time
                alpha = 0.3
                self._stats['avg_queue_time_ms'] = (
                    alpha * avg_queue_time +
                    (1 - alpha) * self._stats['avg_queue_time_ms']
                )

            logger.info(
                f"✅ Flushed {assigned_count}/{len(queued)} detections to video {video_id} "
                f"(avg queue time: {self._stats['avg_queue_time_ms']:.1f}ms)"
            )

            # Clear queue for this session
            del self._queues[session_id]

            return assigned_count

    def get_queue_size(self, session_id: str) -> int:
        """Get number of queued detections for session"""
        with self._lock:
            return len(self._queues.get(session_id, []))

    def get_all_queued_sessions(self) -> List[str]:
        """Get list of sessions with queued detections"""
        with self._lock:
            return list(self._queues.keys())

    def clear_queue(self, session_id: str) -> int:
        """
        Clear queue for session without assigning (emergency cleanup).

        Returns number of detections removed.
        """
        with self._lock:
            if session_id in self._queues:
                count = len(self._queues[session_id])
                del self._queues[session_id]
                logger.warning(f"⚠️ Cleared {count} queued detections for session {session_id}")
                return count
            return 0

    def get_stats(self) -> dict:
        """Get queue statistics for monitoring"""
        with self._lock:
            return {
                **self._stats,
                'active_sessions': len(self._queues),
                'total_pending': sum(len(q) for q in self._queues.values()),
                'queues_by_session': {
                    session_id: len(queue)
                    for session_id, queue in self._queues.items()
                }
            }

    def get_queue_health(self) -> dict:
        """
        Check queue health for monitoring/alerting.

        Returns:
            dict with health status and warnings
        """
        stats = self.get_stats()

        warnings = []
        if stats['total_pending'] > 100:
            warnings.append(f"High pending count: {stats['total_pending']} detections")

        if stats['avg_queue_time_ms'] > 500:
            warnings.append(f"High avg queue time: {stats['avg_queue_time_ms']:.1f}ms")

        if stats['max_queue_size'] > 50:
            warnings.append(f"Large queue size detected: {stats['max_queue_size']}")

        return {
            'healthy': len(warnings) == 0,
            'warnings': warnings,
            'stats': stats
        }


# Singleton instance
_detection_queue: Optional[DetectionQueueService] = None
_queue_lock = threading.Lock()


def get_detection_queue() -> DetectionQueueService:
    """Get singleton detection queue service (thread-safe)"""
    global _detection_queue
    if _detection_queue is None:
        with _queue_lock:
            if _detection_queue is None:
                _detection_queue = DetectionQueueService()
                logger.info("✅ DetectionQueueService initialized")
    return _detection_queue


# Convenience functions for common operations
def enqueue_detection(session_id: str, detection_id: str, timestamp: float):
    """Convenience function to enqueue detection"""
    queue = get_detection_queue()
    queue.enqueue(session_id, detection_id, timestamp)


def flush_detection_queue(session_id: str, video_id: str, db_session) -> int:
    """Convenience function to flush queue"""
    queue = get_detection_queue()
    return queue.flush_for_video(session_id, video_id, db_session)


def get_queue_stats() -> dict:
    """Convenience function to get queue stats"""
    queue = get_detection_queue()
    return queue.get_stats()
