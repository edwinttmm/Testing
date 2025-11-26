"""
Detection Frame Number Fix
===========================

CRITICAL FIX: Calculate frame numbers for detections instead of hardcoding to 0

Root Cause:
-----------
Line 2132-2133 in labjack_detection_service.py hardcodes frame_number=0
This prevents matching detections to ground truth frames, causing 0% coverage

Solution:
---------
Calculate frame_number from:
- Detection timestamp
- Video start time
- Video FPS

Formula: frame_number = int((detection_timestamp - video_start_time) * video_fps)

Usage:
------
1. Import in labjack_detection_service.py:
   from services.detection_frame_number_fix import calculate_frame_number

2. Replace hardcoded frame_number=0 with:
   frame_number=calculate_frame_number(event.timestamp, session, video),

3. Run backfill script for existing sessions:
   python -c "from services.detection_frame_number_fix import backfill_frame_numbers; backfill_frame_numbers('SESSION_ID')"
"""

import logging
from typing import Optional, Tuple
from datetime import datetime
from database import SessionLocal
from models import TestSession, Video, DetectionEvent
from sqlalchemy import and_, or_

logger = logging.getLogger(__name__)


def calculate_frame_number(
    detection_timestamp: float,
    session: TestSession,
    video: Optional[Video] = None
) -> Tuple[int, bool]:
    """
    Calculate frame number from detection timestamp

    Args:
        detection_timestamp: Unix timestamp of detection
        session: TestSession instance
        video: Optional Video instance (will be queried if not provided)

    Returns:
        Tuple of (frame_number, calculation_success)
        - frame_number: Calculated frame (0 if calculation fails)
        - calculation_success: True if calculation succeeded
    """
    try:
        # Get video if not provided
        if video is None:
            db = SessionLocal()
            try:
                video = db.query(Video).filter_by(id=session.video_id).first()
            finally:
                db.close()

        if not video:
            logger.warning(f"Cannot calculate frame number: video not found for session {session.id}")
            return 0, False

        # Get video FPS
        video_fps = video.fps
        if not video_fps or video_fps <= 0:
            logger.warning(f"Invalid video FPS: {video_fps} for video {video.id}")
            return 0, False

        # Get session start time - try multiple field names
        video_start_time = getattr(session, 'video_start_timestamp', None)
        if not video_start_time:
            video_start_time = getattr(session, 'video_playback_start_time', None)
        if not video_start_time:
            video_start_time = getattr(session, 'video_start_time', None)
        if not video_start_time:
            video_start_time = getattr(session, 'start_time', None)

        if not video_start_time:
            logger.warning(f"Cannot calculate frame number: no video start timestamp found for session {session.id}")
            return 0, False

        # Convert to float if datetime
        if isinstance(video_start_time, datetime):
            video_start_time = video_start_time.timestamp()

        # Calculate time offset
        time_offset = detection_timestamp - video_start_time

        # Calculate frame number (0-based)
        frame_number = int(time_offset * video_fps)

        # Validate frame number is reasonable
        if frame_number < 0:
            logger.warning(f"Calculated negative frame number: {frame_number} (detection before video start)")
            return 0, False

        if hasattr(video, 'frame_count') and video.frame_count and frame_number >= video.frame_count:
            logger.warning(f"Calculated frame {frame_number} exceeds video frame count {video.frame_count}")
            # Don't fail - video might still be playing

        logger.debug(
            f"Frame calculation: timestamp={detection_timestamp:.3f}, "
            f"start={video_start_time:.3f}, offset={time_offset:.3f}s, "
            f"fps={video_fps}, frame={frame_number}"
        )

        return frame_number, True

    except Exception as e:
        logger.error(f"Error calculating frame number: {e}")
        return 0, False


def calculate_frame_number_simple(
    detection_timestamp: float,
    video_start_time: float,
    video_fps: float
) -> int:
    """
    Simple frame number calculation (for performance-critical paths)

    Args:
        detection_timestamp: Unix timestamp of detection
        video_start_time: Unix timestamp of video start
        video_fps: Video frames per second

    Returns:
        Calculated frame number (0-based)
    """
    if not video_fps or video_fps <= 0:
        return 0

    time_offset = detection_timestamp - video_start_time
    if time_offset < 0:
        return 0

    return int(time_offset * video_fps)


def backfill_frame_numbers(
    session_id: str,
    dry_run: bool = False
) -> dict:
    """
    Backfill missing frame numbers for existing detections in a session

    Args:
        session_id: Session ID to backfill
        dry_run: If True, only report what would be done without updating

    Returns:
        Dict with statistics:
        - total_detections: Total detections in session
        - missing_frame_numbers: Detections with frame_number=0 or NULL
        - updated: Number of detections updated (if not dry_run)
        - failed: Number of calculations that failed
    """
    db = SessionLocal()
    try:
        # Get session and video
        session = db.query(TestSession).filter_by(id=session_id).first()
        if not session:
            return {"error": f"Session {session_id} not found"}

        video = db.query(Video).filter_by(id=session.video_id).first()
        if not video:
            return {"error": f"Video {session.video_id} not found for session"}

        # Get session start time - try multiple field names
        video_start_time = getattr(session, 'video_start_timestamp', None)
        if not video_start_time:
            video_start_time = getattr(session, 'video_playback_start_time', None)
        if not video_start_time:
            video_start_time = getattr(session, 'video_start_time', None)
        if not video_start_time:
            video_start_time = getattr(session, 'start_time', None)

        if not video_start_time:
            return {"error": f"Session {session_id} has no video start timestamp (checked video_start_timestamp, video_playback_start_time, video_start_time)"}

        if isinstance(video_start_time, datetime):
            video_start_time = video_start_time.timestamp()

        video_fps = video.fps
        if not video_fps or video_fps <= 0:
            return {"error": f"Invalid video FPS: {video_fps}"}

        # Query detections with missing frame numbers
        detections = db.query(DetectionEvent).filter(
            and_(
                DetectionEvent.test_session_id == session_id,
                or_(
                    DetectionEvent.frame_number == None,
                    DetectionEvent.frame_number == 0
                )
            )
        ).all()

        total_count = db.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session_id
        ).count()

        stats = {
            "total_detections": total_count,
            "missing_frame_numbers": len(detections),
            "updated": 0,
            "failed": 0,
            "session_id": session_id,
            "video_fps": video_fps,
            "video_start_time": video_start_time
        }

        if dry_run:
            logger.info(
                f"DRY RUN: Would update {len(detections)}/{total_count} detections "
                f"for session {session_id}"
            )
            return stats

        # Update each detection
        for detection in detections:
            try:
                # Calculate frame number
                frame_number = calculate_frame_number_simple(
                    detection.timestamp,
                    video_start_time,
                    video_fps
                )

                if frame_number >= 0:
                    detection.frame_number = frame_number
                    detection.video_frame_number = frame_number
                    stats["updated"] += 1

                    logger.debug(
                        f"Updated detection {detection.id}: "
                        f"timestamp={detection.timestamp:.3f} → frame={frame_number}"
                    )
                else:
                    stats["failed"] += 1
                    logger.warning(
                        f"Failed to calculate frame for detection {detection.id}: "
                        f"timestamp={detection.timestamp}"
                    )

            except Exception as e:
                stats["failed"] += 1
                logger.error(f"Error updating detection {detection.id}: {e}")

        # Commit changes
        db.commit()

        logger.info(
            f"✅ Backfill complete for session {session_id}: "
            f"updated={stats['updated']}, failed={stats['failed']}, "
            f"total={stats['missing_frame_numbers']}"
        )

        return stats

    except Exception as e:
        db.rollback()
        logger.error(f"Error during backfill: {e}")
        return {"error": str(e)}

    finally:
        db.close()


def backfill_all_sessions(
    dry_run: bool = False,
    limit: Optional[int] = None
) -> dict:
    """
    Backfill frame numbers for all sessions with missing data

    Args:
        dry_run: If True, only report what would be done
        limit: Optionally limit number of sessions to process

    Returns:
        Dict with overall statistics
    """
    db = SessionLocal()
    try:
        # Find sessions with detections missing frame numbers
        query = db.query(TestSession.id).join(
            DetectionEvent,
            DetectionEvent.test_session_id == TestSession.id
        ).filter(
            or_(
                DetectionEvent.frame_number == None,
                DetectionEvent.frame_number == 0
            )
        ).distinct()

        if limit:
            query = query.limit(limit)

        session_ids = [row[0] for row in query.all()]

        overall_stats = {
            "sessions_found": len(session_ids),
            "sessions_processed": 0,
            "total_updated": 0,
            "total_failed": 0,
            "errors": []
        }

        logger.info(f"Found {len(session_ids)} sessions with missing frame numbers")

        for session_id in session_ids:
            logger.info(f"Processing session {session_id}...")

            stats = backfill_frame_numbers(session_id, dry_run=dry_run)

            if "error" in stats:
                overall_stats["errors"].append({
                    "session_id": session_id,
                    "error": stats["error"]
                })
                continue

            overall_stats["sessions_processed"] += 1
            overall_stats["total_updated"] += stats.get("updated", 0)
            overall_stats["total_failed"] += stats.get("failed", 0)

        logger.info(
            f"✅ Backfill complete: processed {overall_stats['sessions_processed']} sessions, "
            f"updated {overall_stats['total_updated']} detections"
        )

        return overall_stats

    finally:
        db.close()


def validate_frame_numbers(session_id: str) -> dict:
    """
    Validate frame numbers for a session

    Returns statistics about frame number quality:
    - total_detections: Total detections
    - with_frame_numbers: Detections with frame_number > 0
    - without_frame_numbers: Detections with frame_number = 0 or NULL
    - coverage_rate: Percentage with valid frame numbers
    """
    db = SessionLocal()
    try:
        total = db.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session_id
        ).count()

        with_frames = db.query(DetectionEvent).filter(
            and_(
                DetectionEvent.test_session_id == session_id,
                DetectionEvent.frame_number != None,
                DetectionEvent.frame_number > 0
            )
        ).count()

        without_frames = total - with_frames
        coverage = (with_frames / total * 100) if total > 0 else 0

        stats = {
            "session_id": session_id,
            "total_detections": total,
            "with_frame_numbers": with_frames,
            "without_frame_numbers": without_frames,
            "coverage_rate": round(coverage, 1)
        }

        logger.info(
            f"Frame number validation for {session_id}: "
            f"{with_frames}/{total} ({coverage:.1f}%) have valid frame numbers"
        )

        return stats

    finally:
        db.close()


# Export main functions
__all__ = [
    'calculate_frame_number',
    'calculate_frame_number_simple',
    'backfill_frame_numbers',
    'backfill_all_sessions',
    'validate_frame_numbers'
]


if __name__ == "__main__":
    # CLI interface for backfilling
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python detection_frame_number_fix.py backfill <session_id> [--dry-run]")
        print("  python detection_frame_number_fix.py backfill-all [--dry-run] [--limit N]")
        print("  python detection_frame_number_fix.py validate <session_id>")
        sys.exit(1)

    command = sys.argv[1]

    if command == "backfill":
        if len(sys.argv) < 3:
            print("Error: session_id required")
            sys.exit(1)

        session_id = sys.argv[2]
        dry_run = "--dry-run" in sys.argv

        print(f"Backfilling frame numbers for session {session_id}...")
        if dry_run:
            print("DRY RUN MODE - no changes will be made")

        stats = backfill_frame_numbers(session_id, dry_run=dry_run)

        print("\nResults:")
        for key, value in stats.items():
            print(f"  {key}: {value}")

    elif command == "backfill-all":
        dry_run = "--dry-run" in sys.argv
        limit = None

        for i, arg in enumerate(sys.argv):
            if arg == "--limit" and i + 1 < len(sys.argv):
                limit = int(sys.argv[i + 1])

        print("Backfilling frame numbers for all sessions...")
        if dry_run:
            print("DRY RUN MODE - no changes will be made")
        if limit:
            print(f"Limiting to {limit} sessions")

        stats = backfill_all_sessions(dry_run=dry_run, limit=limit)

        print("\nResults:")
        for key, value in stats.items():
            print(f"  {key}: {value}")

    elif command == "validate":
        if len(sys.argv) < 3:
            print("Error: session_id required")
            sys.exit(1)

        session_id = sys.argv[2]

        stats = validate_frame_numbers(session_id)

        print("\nValidation Results:")
        for key, value in stats.items():
            print(f"  {key}: {value}")

        if stats["coverage_rate"] < 90:
            print("\n⚠️ WARNING: Coverage rate below 90%")
            print("   Consider running backfill to fix missing frame numbers")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
