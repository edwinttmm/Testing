#!/usr/bin/env python3
"""
Recalculate and update stored recall values in the database using the CORRECT method.

PROBLEM: Sessions store recall using OLD method: TP/(TP+FN)
CORRECT METHOD: TP/actual_gt_count from _get_actual_ground_truth_count()

This script:
1. Queries all test sessions with recall values
2. For each session, gets actual ground truth count from database
3. Recalculates recall using: TP / actual_gt_count
4. Updates database with corrected recall value
5. Provides detailed logging and dry-run mode

Author: AI Model Validation Platform
Date: 2025-11-24
"""

import sys
import os
import argparse
import logging
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from sqlalchemy import func, create_engine
from sqlalchemy.orm import Session, sessionmaker

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import TestSession, GroundTruthObject, Video
from database import get_database_url

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f'recall_recalculation_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)
logger = logging.getLogger(__name__)


class RecallRecalculator:
    """Handles recalculation of recall values using correct ground truth counting method"""

    def __init__(self, database_url: str, dry_run: bool = False):
        """
        Initialize recalculator.

        Args:
            database_url: Database connection URL
            dry_run: If True, don't update database, just show what would change
        """
        self.database_url = database_url
        self.dry_run = dry_run
        self.engine = create_engine(database_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

        logger.info(f"Initialized RecallRecalculator")
        logger.info(f"Database: {self._mask_database_url(database_url)}")
        logger.info(f"Dry-run mode: {dry_run}")

    @staticmethod
    def _mask_database_url(url: str) -> str:
        """Mask password in database URL for logging"""
        import re
        return re.sub(r'://([^:]+):([^@]+)@', r'://\1:***@', url)

    def get_sessions_with_recall(self, db: Session, session_id: Optional[str] = None) -> List[TestSession]:
        """
        Get all test sessions that have recall values.

        Args:
            db: Database session
            session_id: Optional specific session ID to process

        Returns:
            List of TestSession objects with recall values
        """
        query = db.query(TestSession).filter(
            TestSession.accuracy_recall.isnot(None),
            TestSession.tp_count.isnot(None)
        )

        if session_id:
            query = query.filter(TestSession.id == session_id)

        sessions = query.all()
        logger.info(f"Found {len(sessions)} sessions with recall values")
        return sessions

    def get_actual_ground_truth_count(
        self,
        db: Session,
        test_session: TestSession
    ) -> Tuple[int, Dict[str, int]]:
        """
        Get actual ground truth count using the CORRECT method from ground_truth_matching_service.py.

        This is the fixed implementation that counts ALL GT objects for the video(s) in the session,
        not just the ones that were matched.

        Args:
            db: Database session
            test_session: Test session object

        Returns:
            Tuple of (total_gt_count, video_gt_counts_dict)
        """
        video_gt_counts = {}

        try:
            # Determine which videos to count GT objects for
            if test_session.has_video_sequence and test_session.sequence_id:
                # Multi-video session: count GT across all videos in sequence
                if test_session.sequence_metadata and 'video_ids' in test_session.sequence_metadata:
                    video_ids = test_session.sequence_metadata['video_ids']
                else:
                    # Fallback to session video_id if sequence has no videos
                    video_ids = [test_session.video_id] if test_session.video_id else []

                if not video_ids:
                    logger.warning(f"No video IDs found for multi-video session {test_session.id}")
                    return 0, {}

                # Count GT objects for each video
                for video_id in video_ids:
                    gt_count = db.query(func.count(GroundTruthObject.id)).filter(
                        GroundTruthObject.video_id == video_id,
                        GroundTruthObject.deleted_at.is_(None)  # Exclude soft-deleted
                    ).scalar() or 0
                    video_gt_counts[video_id] = gt_count

                total_gt_count = sum(video_gt_counts.values())

                logger.debug(
                    f"Multi-video session {test_session.id[:8]}: "
                    f"{total_gt_count} GT objects across {len(video_ids)} videos"
                )
                return total_gt_count, video_gt_counts

            else:
                # Single video session: count GT for just this video
                if not test_session.video_id:
                    logger.warning(f"No video_id found for single-video session {test_session.id}")
                    return 0, {}

                gt_count = db.query(func.count(GroundTruthObject.id)).filter(
                    GroundTruthObject.video_id == test_session.video_id,
                    GroundTruthObject.deleted_at.is_(None)  # Exclude soft-deleted
                ).scalar() or 0

                video_gt_counts[test_session.video_id] = gt_count

                logger.debug(
                    f"Single video session {test_session.id[:8]}: "
                    f"{gt_count} GT objects for video {test_session.video_id[:8]}"
                )
                return gt_count, video_gt_counts

        except Exception as e:
            logger.error(
                f"Failed to count ground truth objects for session {test_session.id}: {e}",
                exc_info=True
            )
            return 0, {}

    def calculate_correct_recall(self, tp_count: int, actual_gt_count: int) -> Optional[float]:
        """
        Calculate recall using the CORRECT formula: TP / actual_gt_count

        Args:
            tp_count: True positive count
            actual_gt_count: Actual ground truth count from database

        Returns:
            Recall value (0.0 to 1.0) or None if calculation not possible
        """
        if actual_gt_count == 0:
            logger.warning(f"Cannot calculate recall: actual_gt_count is 0")
            return None

        if tp_count < 0 or tp_count > actual_gt_count:
            logger.warning(
                f"Invalid TP count: {tp_count} (GT count: {actual_gt_count}). "
                f"TP should be between 0 and GT count."
            )

        recall = tp_count / actual_gt_count
        return round(recall, 4)  # Round to 4 decimal places

    def get_video_names(self, db: Session, video_ids: List[str]) -> Dict[str, str]:
        """Get video filenames for display purposes"""
        video_names = {}
        videos = db.query(Video).filter(Video.id.in_(video_ids)).all()
        for video in videos:
            video_names[video.id] = video.filename
        return video_names

    def recalculate_session(
        self,
        db: Session,
        test_session: TestSession
    ) -> Dict:
        """
        Recalculate recall for a single test session.

        Args:
            db: Database session
            test_session: Test session to recalculate

        Returns:
            Dictionary with recalculation results
        """
        session_id_short = test_session.id[:8]

        # Get current values
        old_recall = test_session.accuracy_recall
        tp_count = test_session.tp_count or 0
        fn_count = test_session.fn_count or 0

        # Get actual ground truth count using CORRECT method
        actual_gt_count, video_gt_counts = self.get_actual_ground_truth_count(db, test_session)

        if actual_gt_count == 0:
            logger.warning(
                f"Session {session_id_short}: No ground truth data found. "
                f"Cannot recalculate recall."
            )
            return {
                'session_id': test_session.id,
                'status': 'skipped',
                'reason': 'no_ground_truth_data',
                'old_recall': old_recall,
                'new_recall': None
            }

        # Calculate correct recall
        new_recall = self.calculate_correct_recall(tp_count, actual_gt_count)

        if new_recall is None:
            return {
                'session_id': test_session.id,
                'status': 'error',
                'reason': 'calculation_failed',
                'old_recall': old_recall,
                'new_recall': None
            }

        # Calculate what the OLD incorrect method would have given
        old_method_denominator = tp_count + fn_count
        old_method_recall = tp_count / old_method_denominator if old_method_denominator > 0 else 0

        # Prepare result
        result = {
            'session_id': test_session.id,
            'session_name': test_session.name,
            'status': 'updated' if not self.dry_run else 'would_update',
            'tp_count': tp_count,
            'fn_count': fn_count,
            'actual_gt_count': actual_gt_count,
            'video_gt_counts': video_gt_counts,
            'old_recall': old_recall,
            'new_recall': new_recall,
            'old_method_recall': old_method_recall,
            'difference': round(new_recall - (old_recall or 0), 4),
            'has_video_sequence': test_session.has_video_sequence
        }

        # Update database if not dry-run
        if not self.dry_run and new_recall != old_recall:
            test_session.accuracy_recall = new_recall
            db.commit()
            logger.info(f"✅ Updated session {session_id_short}: recall {old_recall} → {new_recall}")

        return result

    def format_session_result(self, result: Dict, video_names: Dict[str, str]) -> str:
        """Format a single session result for display"""
        lines = []
        session_id_short = result['session_id'][:8]

        lines.append(f"\n{'='*80}")
        lines.append(f"Session {result['session_id']}")
        lines.append(f"Name: {result.get('session_name', 'N/A')}")
        lines.append(f"{'='*80}")

        # Video information
        if result['has_video_sequence']:
            lines.append(f"Type: Multi-video sequence")
            lines.append(f"Videos:")
            for video_id, gt_count in result.get('video_gt_counts', {}).items():
                video_name = video_names.get(video_id, video_id[:8])
                lines.append(f"  - {video_name}: {gt_count} GT events")
        else:
            video_id = list(result.get('video_gt_counts', {}).keys())[0] if result.get('video_gt_counts') else None
            video_name = video_names.get(video_id, video_id[:8] if video_id else 'N/A')
            gt_count = result.get('actual_gt_count', 0)
            lines.append(f"Type: Single video")
            lines.append(f"Video: {video_name}")
            lines.append(f"Ground Truth Events: {gt_count}")

        # Metrics
        lines.append(f"\nMetrics:")
        lines.append(f"  Total GT Events: {result.get('actual_gt_count', 0)}")
        lines.append(f"  True Positives (TP): {result.get('tp_count', 0)}")
        lines.append(f"  False Negatives (FN): {result.get('fn_count', 0)}")

        # Recall comparison
        lines.append(f"\nRecall Calculation:")
        old_recall = result.get('old_recall')
        new_recall = result.get('new_recall')
        old_method_recall = result.get('old_method_recall')

        if old_recall is not None:
            lines.append(f"  Old Stored Value: {old_recall:.4f} ({old_recall*100:.2f}%)")

        if old_method_recall is not None:
            tp = result.get('tp_count', 0)
            fn = result.get('fn_count', 0)
            lines.append(f"  OLD METHOD: {old_method_recall:.4f} = {tp}/({tp}+{fn}) - WRONG!")

        if new_recall is not None:
            tp = result.get('tp_count', 0)
            gt = result.get('actual_gt_count', 0)
            lines.append(f"  NEW METHOD: {new_recall:.4f} = {tp}/{gt} - CORRECT ✓")
            lines.append(f"  New Recall: {new_recall:.4f} ({new_recall*100:.2f}%)")

        if old_recall is not None and new_recall is not None:
            diff = result.get('difference', 0)
            if abs(diff) > 0.0001:
                arrow = "↑" if diff > 0 else "↓"
                lines.append(f"  Change: {arrow} {abs(diff):.4f} ({abs(diff)*100:.2f} percentage points)")
            else:
                lines.append(f"  Change: No change")

        # Status
        status = result.get('status', 'unknown')
        if status == 'updated':
            lines.append(f"\n✅ Updated")
        elif status == 'would_update':
            lines.append(f"\n🔍 Would update (dry-run mode)")
        elif status == 'skipped':
            reason = result.get('reason', 'unknown')
            lines.append(f"\n⚠️  Skipped: {reason}")
        elif status == 'error':
            reason = result.get('reason', 'unknown')
            lines.append(f"\n❌ Error: {reason}")

        return '\n'.join(lines)

    def run(self, session_id: Optional[str] = None) -> Dict:
        """
        Run the recall recalculation for all sessions or a specific session.

        Args:
            session_id: Optional specific session ID to process

        Returns:
            Dictionary with overall statistics
        """
        logger.info("Starting recall recalculation...")

        with self.SessionLocal() as db:
            # Get sessions to process
            sessions = self.get_sessions_with_recall(db, session_id)

            if not sessions:
                logger.warning("No sessions found with recall values to recalculate")
                return {
                    'total_sessions': 0,
                    'updated': 0,
                    'skipped': 0,
                    'errors': 0
                }

            # Collect all video IDs for name lookup
            all_video_ids = set()
            for session in sessions:
                if session.video_id:
                    all_video_ids.add(session.video_id)
                if session.has_video_sequence and session.sequence_metadata:
                    video_ids = session.sequence_metadata.get('video_ids', [])
                    all_video_ids.update(video_ids)

            video_names = self.get_video_names(db, list(all_video_ids))

            # Process each session
            results = []
            stats = {
                'total_sessions': len(sessions),
                'updated': 0,
                'skipped': 0,
                'errors': 0,
                'no_change': 0
            }

            for session in sessions:
                try:
                    result = self.recalculate_session(db, session)
                    results.append(result)

                    # Update statistics
                    status = result.get('status', 'error')
                    if status in ['updated', 'would_update']:
                        if abs(result.get('difference', 0)) < 0.0001:
                            stats['no_change'] += 1
                        else:
                            stats['updated'] += 1
                    elif status == 'skipped':
                        stats['skipped'] += 1
                    else:
                        stats['errors'] += 1

                    # Print result
                    print(self.format_session_result(result, video_names))

                except Exception as e:
                    logger.error(f"Error processing session {session.id}: {e}", exc_info=True)
                    stats['errors'] += 1

            # Print summary
            print(f"\n{'='*80}")
            print("SUMMARY")
            print(f"{'='*80}")
            print(f"Total sessions processed: {stats['total_sessions']}")
            print(f"Sessions updated: {stats['updated']}")
            print(f"Sessions with no change: {stats['no_change']}")
            print(f"Sessions skipped: {stats['skipped']}")
            print(f"Errors: {stats['errors']}")

            if self.dry_run:
                print(f"\n🔍 DRY-RUN MODE: No changes were made to the database")
            else:
                print(f"\n✅ Database updated with corrected recall values")

            return stats


def main():
    """Main entry point for the script"""
    parser = argparse.ArgumentParser(
        description='Recalculate and update stored recall values using correct ground truth counting method',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview changes without updating database
  python recalculate_recall_values.py --dry-run

  # Update all sessions
  python recalculate_recall_values.py

  # Update specific session
  python recalculate_recall_values.py --session-id 2c9a93f6-8471-4f2e-b1a7-06f239fca548

  # Use custom database
  python recalculate_recall_values.py --database sqlite:///./test.db
        """
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without updating the database'
    )

    parser.add_argument(
        '--session-id',
        type=str,
        help='Recalculate recall for a specific session ID only'
    )

    parser.add_argument(
        '--database',
        type=str,
        default=None,
        help='Database URL (default: from environment or dev_database.db)'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Get database URL
    database_url = args.database or get_database_url()

    # Create recalculator and run
    recalculator = RecallRecalculator(database_url, dry_run=args.dry_run)

    try:
        stats = recalculator.run(session_id=args.session_id)

        # Exit with appropriate code
        if stats['errors'] > 0:
            sys.exit(1)
        else:
            sys.exit(0)

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(2)


if __name__ == '__main__':
    main()
