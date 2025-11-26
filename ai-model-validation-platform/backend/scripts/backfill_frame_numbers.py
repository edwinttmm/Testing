#!/usr/bin/env python3
"""
Production Script: Backfill Frame Numbers for Existing Detections

This script fixes historical detection events that have NULL or 0 frame_number
by calculating the correct frame number from timestamps and video FPS.

Usage:
    # Fix specific session
    python backfill_frame_numbers.py --session-id <session_id>

    # Fix all sessions with missing frame numbers
    python backfill_frame_numbers.py --all

    # Dry run (preview changes without committing)
    python backfill_frame_numbers.py --session-id <session_id> --dry-run

    # With rollback support
    python backfill_frame_numbers.py --session-id <session_id> --create-backup

Author: Frame Number Fix Specialist
Date: 2025-11-20
"""

import sys
import argparse
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, or_, and_
from sqlalchemy.orm import sessionmaker, Session
from database import get_db, SessionLocal
from models import DetectionEvent, TestSession, Video

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FrameNumberBackfillService:
    """Service to backfill missing frame numbers in detection events"""

    def __init__(self, db: Session):
        self.db = db

    def calculate_frame_number(
        self,
        detection_timestamp: float,
        video_relative_timestamp: Optional[float],
        video_start_time: Optional[float],
        fps: float
    ) -> Optional[int]:
        """
        Calculate frame number from timestamp and video metadata.

        Args:
            detection_timestamp: Unix timestamp of detection
            video_relative_timestamp: Video-relative timestamp (preferred)
            video_start_time: Video playback start time
            fps: Video frames per second

        Returns:
            Calculated frame number or None if cannot calculate
        """
        try:
            # Method 1: Use video_relative_timestamp (most accurate)
            if video_relative_timestamp is not None:
                frame_number = int(video_relative_timestamp * fps)
                logger.debug(f"Frame calculated from video_relative_timestamp: {frame_number}")
                return frame_number

            # Method 2: Calculate from absolute timestamp and video start
            if detection_timestamp and video_start_time:
                time_offset = detection_timestamp - video_start_time
                if time_offset < 0:
                    logger.warning(f"Negative time offset: {time_offset}s (detection before video start)")
                    return None
                frame_number = int(time_offset * fps)
                logger.debug(f"Frame calculated from timestamp offset: {frame_number}")
                return frame_number

            # Cannot calculate
            logger.warning(f"Cannot calculate frame: ts={detection_timestamp}, video_start={video_start_time}")
            return None

        except Exception as e:
            logger.error(f"Error calculating frame number: {e}")
            return None

    def get_video_fps(self, session: TestSession, video_id: Optional[str]) -> float:
        """
        Get video FPS from session or video metadata.

        Args:
            session: Test session object
            video_id: Video ID

        Returns:
            FPS value (defaults to 24.0 if not found)
        """
        # Try session.video_fps first
        if hasattr(session, 'video_fps') and session.video_fps:
            return session.video_fps

        # Fallback to video metadata
        if video_id:
            video = self.db.query(Video).filter(Video.id == video_id).first()
            if video and hasattr(video, 'video_fps') and video.video_fps:
                return video.video_fps

        # Default fallback
        logger.warning(f"No FPS found for session {session.id}, using default: 24.0")
        return 24.0

    def backfill_session(
        self,
        session_id: str,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Backfill frame numbers for all detections in a session.

        Args:
            session_id: Test session ID
            dry_run: If True, preview changes without committing

        Returns:
            Dictionary with statistics about the backfill
        """
        logger.info(f"Starting backfill for session: {session_id} (dry_run={dry_run})")

        # Get session
        session = self.db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        # Get detections with missing frame numbers
        detections = self.db.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session_id,
            or_(
                DetectionEvent.frame_number == None,
                DetectionEvent.frame_number == 0
            )
        ).all()

        logger.info(f"Found {len(detections)} detections with missing frame numbers")

        # Get video start time and FPS
        video_start_time = session.video_playback_start_time if hasattr(session, 'video_playback_start_time') else None

        # Track statistics
        stats = {
            'session_id': session_id,
            'total_detections': len(detections),
            'updated': 0,
            'failed': 0,
            'skipped': 0,
            'dry_run': dry_run
        }

        # Process each detection
        for detection in detections:
            try:
                # Get FPS for this detection's video
                fps = self.get_video_fps(session, detection.video_id)

                # Calculate frame number
                frame_number = self.calculate_frame_number(
                    detection_timestamp=detection.timestamp,
                    video_relative_timestamp=detection.video_relative_timestamp if hasattr(detection, 'video_relative_timestamp') else None,
                    video_start_time=video_start_time,
                    fps=fps
                )

                if frame_number is not None:
                    if not dry_run:
                        # Update detection
                        detection.frame_number = frame_number
                        detection.video_frame_number = frame_number

                        # Update metadata
                        if detection.detection_metadata is None:
                            detection.detection_metadata = {}
                        detection.detection_metadata['frame_backfill_timestamp'] = datetime.utcnow().isoformat()
                        detection.detection_metadata['frame_backfill_fps'] = fps

                    stats['updated'] += 1
                    logger.debug(f"Updated detection {detection.id}: frame_number={frame_number}")
                else:
                    stats['skipped'] += 1
                    logger.warning(f"Skipped detection {detection.id}: Cannot calculate frame number")

            except Exception as e:
                stats['failed'] += 1
                logger.error(f"Failed to update detection {detection.id}: {e}")

        # Commit changes
        if not dry_run and stats['updated'] > 0:
            self.db.commit()
            logger.info(f"Committed {stats['updated']} frame number updates")
        elif dry_run:
            logger.info(f"DRY RUN: Would update {stats['updated']} detections")

        return stats

    def backfill_all_sessions(self, dry_run: bool = False) -> List[Dict[str, Any]]:
        """
        Backfill frame numbers for all sessions with missing data.

        Args:
            dry_run: If True, preview changes without committing

        Returns:
            List of statistics dictionaries for each session
        """
        logger.info(f"Starting backfill for all sessions (dry_run={dry_run})")

        # Find all sessions with detections missing frame numbers
        sessions_with_missing = self.db.query(TestSession).join(
            DetectionEvent,
            DetectionEvent.test_session_id == TestSession.id
        ).filter(
            or_(
                DetectionEvent.frame_number == None,
                DetectionEvent.frame_number == 0
            )
        ).distinct().all()

        logger.info(f"Found {len(sessions_with_missing)} sessions with missing frame numbers")

        all_stats = []
        for session in sessions_with_missing:
            try:
                stats = self.backfill_session(session.id, dry_run=dry_run)
                all_stats.append(stats)
            except Exception as e:
                logger.error(f"Failed to backfill session {session.id}: {e}")
                all_stats.append({
                    'session_id': session.id,
                    'error': str(e)
                })

        return all_stats

    def validate_session(self, session_id: str) -> Dict[str, Any]:
        """
        Validate frame number coverage for a session.

        Args:
            session_id: Test session ID

        Returns:
            Validation statistics
        """
        logger.info(f"Validating frame numbers for session: {session_id}")

        # Count total detections
        total = self.db.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session_id
        ).count()

        # Count detections with valid frame numbers
        with_frame = self.db.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session_id,
            DetectionEvent.frame_number != None,
            DetectionEvent.frame_number > 0
        ).count()

        # Count detections missing frame numbers
        without_frame = self.db.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session_id,
            or_(
                DetectionEvent.frame_number == None,
                DetectionEvent.frame_number == 0
            )
        ).count()

        coverage_rate = (with_frame / total * 100) if total > 0 else 0

        validation = {
            'session_id': session_id,
            'total_detections': total,
            'with_frame_number': with_frame,
            'without_frame_number': without_frame,
            'coverage_rate': round(coverage_rate, 2)
        }

        logger.info(f"Validation: {with_frame}/{total} detections have frame numbers ({coverage_rate:.1f}%)")

        return validation


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Backfill frame numbers for detection events',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '--session-id',
        type=str,
        help='Session ID to backfill'
    )

    parser.add_argument(
        '--all',
        action='store_true',
        help='Backfill all sessions with missing frame numbers'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without committing'
    )

    parser.add_argument(
        '--validate',
        action='store_true',
        help='Validate frame number coverage (use with --session-id)'
    )

    parser.add_argument(
        '--create-backup',
        action='store_true',
        help='Create database backup before backfilling (recommended)'
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.session_id and not args.all:
        parser.error("Must specify either --session-id or --all")

    if args.session_id and args.all:
        parser.error("Cannot specify both --session-id and --all")

    # Create backup if requested
    if args.create_backup and not args.dry_run:
        logger.info("Creating database backup...")
        try:
            from backup_utils import create_backup
            backup_path = create_backup()
            logger.info(f"Backup created: {backup_path}")
        except ImportError:
            logger.warning("Backup utility not available, skipping backup")
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            sys.exit(1)

    # Get database session
    db = SessionLocal()
    service = FrameNumberBackfillService(db)

    try:
        # Execute requested operation
        if args.validate:
            if not args.session_id:
                parser.error("--validate requires --session-id")

            validation = service.validate_session(args.session_id)
            print("\n" + "="*60)
            print("FRAME NUMBER VALIDATION REPORT")
            print("="*60)
            print(f"Session ID: {validation['session_id']}")
            print(f"Total Detections: {validation['total_detections']}")
            print(f"With Frame Number: {validation['with_frame_number']}")
            print(f"Without Frame Number: {validation['without_frame_number']}")
            print(f"Coverage Rate: {validation['coverage_rate']}%")
            print("="*60 + "\n")

        elif args.session_id:
            # Backfill single session
            stats = service.backfill_session(args.session_id, dry_run=args.dry_run)

            print("\n" + "="*60)
            print("BACKFILL REPORT")
            print("="*60)
            print(f"Session ID: {stats['session_id']}")
            print(f"Total Detections: {stats['total_detections']}")
            print(f"Updated: {stats['updated']}")
            print(f"Failed: {stats['failed']}")
            print(f"Skipped: {stats['skipped']}")
            print(f"Dry Run: {stats['dry_run']}")
            print("="*60 + "\n")

            # Validate after backfill
            if not args.dry_run and stats['updated'] > 0:
                validation = service.validate_session(args.session_id)
                print(f"Post-backfill coverage: {validation['coverage_rate']}%\n")

        elif args.all:
            # Backfill all sessions
            all_stats = service.backfill_all_sessions(dry_run=args.dry_run)

            print("\n" + "="*60)
            print("BATCH BACKFILL REPORT")
            print("="*60)
            print(f"Sessions Processed: {len(all_stats)}")

            total_updated = sum(s.get('updated', 0) for s in all_stats)
            total_failed = sum(s.get('failed', 0) for s in all_stats)
            total_skipped = sum(s.get('skipped', 0) for s in all_stats)

            print(f"Total Updated: {total_updated}")
            print(f"Total Failed: {total_failed}")
            print(f"Total Skipped: {total_skipped}")
            print(f"Dry Run: {args.dry_run}")
            print("="*60)

            # Show per-session details
            print("\nPer-Session Details:")
            for stats in all_stats:
                if 'error' in stats:
                    print(f"  {stats['session_id']}: ERROR - {stats['error']}")
                else:
                    print(f"  {stats['session_id']}: {stats['updated']} updated, {stats['failed']} failed, {stats['skipped']} skipped")
            print()

    except Exception as e:
        logger.error(f"Backfill failed: {e}", exc_info=True)
        sys.exit(1)

    finally:
        db.close()


if __name__ == '__main__':
    main()
