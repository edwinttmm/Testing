#!/usr/bin/env python3
"""
Backfill Script: Fix NULL video_ids in Detection Events

This script fixes the race condition issue where detection events were stored with NULL video_id
because they arrived before video lifecycle events (onPlay) were processed by the frontend.

The fix retrospectively assigns correct video_ids to detections using:
1. Video timing boundaries from SequenceVideoResult records
2. Detection timestamps to determine which video was playing
3. Per-video time ranges calculated from video_start_time and duration

Usage:
    # Dry run (preview changes without committing):
    python3 scripts/backfill_null_video_ids.py --session-id <SESSION_ID> --dry-run

    # Apply fixes:
    python3 scripts/backfill_null_video_ids.py --session-id <SESSION_ID>

    # Process all sessions with NULL video_ids:
    python3 scripts/backfill_null_video_ids.py --all

    # Process specific session example:
    python3 scripts/backfill_null_video_ids.py --session-id 0846e476

Author: AI Model Validation Platform Team
Date: 2025-01-04
Issue: Race condition causing 501/502 detections with NULL video_id in session 0846e476
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import text
from database import SessionLocal
from services.detection_video_reassignment import reassign_null_video_ids
from models import TestSession, DetectionEvent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(backend_dir / "logs" / "backfill_null_video_ids.log")
    ]
)
logger = logging.getLogger(__name__)


def find_sessions_with_null_video_ids(min_null_count: int = 1) -> List[Dict[str, Any]]:
    """
    Find all sessions with detections that have NULL video_id.

    Args:
        min_null_count: Minimum number of NULL detections to include session

    Returns:
        List of dicts with session_id, null_count, total_count, percentage
    """
    db = SessionLocal()
    try:
        query = text('''
            SELECT
                de.test_session_id as session_id,
                COUNT(*) as null_count,
                (SELECT COUNT(*) FROM detection_events de2
                 WHERE de2.test_session_id = de.test_session_id) as total_count,
                ts.status as session_status,
                ts.has_video_sequence as has_sequence
            FROM detection_events de
            LEFT JOIN test_sessions ts ON ts.id = de.test_session_id
            WHERE de.video_id IS NULL
            GROUP BY de.test_session_id, ts.status, ts.has_video_sequence
            HAVING null_count >= :min_count
            ORDER BY null_count DESC
        ''')

        result = db.execute(query, {"min_count": min_null_count}).fetchall()

        sessions = []
        for row in result:
            session_id, null_count, total_count, status, has_sequence = row
            percentage = (null_count / total_count * 100) if total_count > 0 else 0

            sessions.append({
                "session_id": session_id,
                "null_count": null_count,
                "total_count": total_count,
                "percentage": percentage,
                "status": status,
                "has_sequence": bool(has_sequence)
            })

        return sessions

    finally:
        db.close()


async def backfill_session(session_id: str, dry_run: bool = True) -> Dict[str, Any]:
    """
    Run video_id reassignment for a specific session.

    Args:
        session_id: Session ID to process
        dry_run: If True, preview changes without committing

    Returns:
        Dict with reassignment results
    """
    logger.info(f"{'[DRY RUN] ' if dry_run else ''}Processing session {session_id}")

    try:
        result = await reassign_null_video_ids(session_id, dry_run=dry_run)

        if result["success"]:
            reassigned = result.get("reassigned_count", 0)
            corrected = result.get("corrected_existing", 0)
            total = result.get("total_detections", 0)

            logger.info(
                f"{'[DRY RUN] ' if dry_run else '✅ '}Session {session_id} results:\n"
                f"  - Reassigned NULL detections: {reassigned}\n"
                f"  - Corrected existing assignments: {corrected}\n"
                f"  - Total detections: {total}\n"
                f"  - Video assignments: {result.get('video_assignments', {})}"
            )

            if result.get("errors"):
                logger.warning(f"  - Errors: {len(result['errors'])} errors occurred")
                for error in result["errors"][:5]:  # Show first 5 errors
                    logger.warning(f"    • {error}")

            return result
        else:
            error = result.get("error", "Unknown error")
            logger.error(f"❌ Failed to process session {session_id}: {error}")
            return result

    except Exception as e:
        logger.error(f"❌ Exception processing session {session_id}: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "session_id": session_id
        }


async def backfill_all_sessions(dry_run: bool = True, min_null_count: int = 1):
    """
    Run video_id reassignment for all sessions with NULL video_ids.

    Args:
        dry_run: If True, preview changes without committing
        min_null_count: Minimum number of NULL detections to process session
    """
    logger.info(f"{'[DRY RUN] ' if dry_run else ''}Finding sessions with NULL video_ids...")

    sessions = find_sessions_with_null_video_ids(min_null_count)

    if not sessions:
        logger.info("No sessions found with NULL video_ids")
        return

    logger.info(f"Found {len(sessions)} sessions with NULL video_ids:")
    for session_info in sessions:
        logger.info(
            f"  • {session_info['session_id']}: {session_info['null_count']}/{session_info['total_count']} "
            f"({session_info['percentage']:.1f}% NULL) - status: {session_info['status']}"
        )

    print("\n" + "="*80)

    # Process each session
    total_reassigned = 0
    total_corrected = 0
    successful_sessions = 0
    failed_sessions = 0

    for i, session_info in enumerate(sessions, 1):
        session_id = session_info["session_id"]

        print(f"\nProcessing session {i}/{len(sessions)}: {session_id}")
        print("-" * 80)

        result = await backfill_session(session_id, dry_run=dry_run)

        if result.get("success"):
            successful_sessions += 1
            total_reassigned += result.get("reassigned_count", 0)
            total_corrected += result.get("corrected_existing", 0)
        else:
            failed_sessions += 1

    # Summary
    print("\n" + "="*80)
    print(f"{'[DRY RUN] ' if dry_run else ''}BACKFILL SUMMARY")
    print("="*80)
    print(f"Sessions processed: {len(sessions)}")
    print(f"  ✅ Successful: {successful_sessions}")
    print(f"  ❌ Failed: {failed_sessions}")
    print(f"Total NULL detections reassigned: {total_reassigned}")
    print(f"Total existing assignments corrected: {total_corrected}")

    if dry_run:
        print("\n⚠️ This was a DRY RUN - no changes were committed to the database.")
        print("Run without --dry-run to apply the changes.")


async def verify_session_fix(session_id: str):
    """
    Verify that a session has been fixed and no longer has NULL video_ids.

    Args:
        session_id: Session ID to verify
    """
    db = SessionLocal()
    try:
        # Check for remaining NULL video_ids
        result = db.execute(
            text('SELECT COUNT(*) FROM detection_events WHERE test_session_id = :sid AND video_id IS NULL'),
            {"sid": session_id}
        ).fetchone()

        null_count = result[0] if result else 0

        # Get total detection count
        result = db.execute(
            text('SELECT COUNT(*) FROM detection_events WHERE test_session_id = :sid'),
            {"sid": session_id}
        ).fetchone()

        total_count = result[0] if result else 0

        # Get video_id distribution
        result = db.execute(
            text('SELECT video_id, COUNT(*) FROM detection_events WHERE test_session_id = :sid GROUP BY video_id'),
            {"sid": session_id}
        ).fetchall()

        print(f"\n{'='*80}")
        print(f"VERIFICATION REPORT: Session {session_id}")
        print(f"{'='*80}")
        print(f"Total detections: {total_count}")
        print(f"NULL video_ids: {null_count}")

        if null_count == 0:
            print("✅ SUCCESS: All detections have valid video_ids")
        else:
            print(f"⚠️ WARNING: {null_count} detections still have NULL video_ids")

        print(f"\nVideo ID distribution:")
        for row in result:
            video_id = row[0] if row[0] else 'NULL'
            count = row[1]
            percentage = (count / total_count * 100) if total_count > 0 else 0
            print(f"  • {video_id}: {count} detections ({percentage:.1f}%)")

        return null_count == 0

    finally:
        db.close()


def main():
    """Main entry point for backfill script."""
    parser = argparse.ArgumentParser(
        description="Backfill NULL video_ids in detection events using timing analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview changes for specific session:
  python3 scripts/backfill_null_video_ids.py --session-id 0846e476 --dry-run

  # Apply fix for specific session:
  python3 scripts/backfill_null_video_ids.py --session-id 0846e476

  # Preview changes for all sessions:
  python3 scripts/backfill_null_video_ids.py --all --dry-run

  # Apply fix for all sessions:
  python3 scripts/backfill_null_video_ids.py --all

  # Verify session after fix:
  python3 scripts/backfill_null_video_ids.py --session-id 0846e476 --verify
        """
    )

    parser.add_argument(
        "--session-id",
        type=str,
        help="Specific session ID to process"
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all sessions with NULL video_ids"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without committing to database"
    )

    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify session has been fixed (use with --session-id)"
    )

    parser.add_argument(
        "--min-null-count",
        type=int,
        default=1,
        help="Minimum number of NULL detections to process session (default: 1)"
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.session_id and not args.all:
        parser.error("Must specify either --session-id or --all")

    if args.session_id and args.all:
        parser.error("Cannot specify both --session-id and --all")

    if args.verify and not args.session_id:
        parser.error("--verify requires --session-id")

    # Run appropriate operation
    try:
        if args.verify:
            # Verification mode
            success = asyncio.run(verify_session_fix(args.session_id))
            sys.exit(0 if success else 1)

        elif args.session_id:
            # Single session mode
            result = asyncio.run(backfill_session(args.session_id, dry_run=args.dry_run))

            if result.get("success"):
                # Verify fix
                print("\n" + "="*80)
                asyncio.run(verify_session_fix(args.session_id))
                sys.exit(0)
            else:
                sys.exit(1)

        else:
            # All sessions mode
            asyncio.run(backfill_all_sessions(dry_run=args.dry_run, min_null_count=args.min_null_count))
            sys.exit(0)

    except KeyboardInterrupt:
        logger.info("\nBackfill interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
