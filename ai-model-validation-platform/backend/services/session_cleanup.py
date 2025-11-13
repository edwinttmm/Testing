"""
Session Cleanup Service

Periodic background job to clean up stale sessions and mark them as failed.
Prevents sessions from remaining in "running" state indefinitely when frontend
disconnects or test execution hangs.

CRITICAL FIX: Implements automatic session timeout and cleanup to prevent
sessions from being stuck in limbo state forever.
"""

import logging
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import Session
from database import SessionLocal
from models import TestSession

logger = logging.getLogger(__name__)

# Configuration
STALE_SESSION_TIMEOUT_HOURS = 2  # Mark sessions as stale after 2 hours
CLEANUP_INTERVAL_HOURS = 1  # Run cleanup job every hour

def cleanup_stale_sessions():
    """
    Mark old running sessions as failed.

    This handles cases where:
    - Frontend disconnected before completing session
    - Video lifecycle events never fired
    - LabJack monitoring crashed
    - Network issues prevented completion

    Sessions in "running" state for more than STALE_SESSION_TIMEOUT_HOURS
    are automatically marked as "error" with appropriate failure details.
    """
    try:
        db = SessionLocal()
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=STALE_SESSION_TIMEOUT_HOURS)

            # Find stale sessions
            stale_sessions = db.query(TestSession).filter(
                TestSession.status == "running",
                TestSession.started_at < cutoff_time
            ).all()

            if not stale_sessions:
                logger.debug(f"No stale sessions found (cutoff: {cutoff_time.isoformat()})")
                return

            logger.warning(
                f"Found {len(stale_sessions)} stale sessions running longer than "
                f"{STALE_SESSION_TIMEOUT_HOURS} hours"
            )

            for session in stale_sessions:
                runtime_hours = (datetime.now(timezone.utc) - session.started_at).total_seconds() / 3600

                logger.warning(
                    f"Marking stale session {session.id} as failed "
                    f"(running for {runtime_hours:.1f} hours)"
                )

                session.status = "error"
                session.failure_reason = (
                    f"Session timeout - exceeded {STALE_SESSION_TIMEOUT_HOURS} hour limit. "
                    f"Session was running for {runtime_hours:.1f} hours without completion."
                )
                session.failed_at = datetime.now(timezone.utc)
                session.failure_details = {
                    'error_type': 'session_timeout',
                    'timeout_hours': STALE_SESSION_TIMEOUT_HOURS,
                    'actual_runtime_hours': runtime_hours,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'recoverable': False,  # Stale sessions should not be retried
                    'cleanup_reason': 'automatic_timeout_cleanup'
                }

                # Emit WebSocket event if possible
                try:
                    from socketio_server import sio
                    import asyncio
                    asyncio.create_task(
                        sio.emit('session_failed', {
                            'session_id': session.id,
                            'status': 'error',
                            'reason': 'session_timeout',
                            'message': session.failure_reason,
                            'recoverable': False
                        })
                    )
                except Exception as ws_error:
                    logger.warning(f"Could not emit timeout WebSocket event: {ws_error}")

            db.commit()

            logger.info(
                f"Cleanup complete: marked {len(stale_sessions)} stale sessions as failed"
            )

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error during session cleanup: {e}", exc_info=True)

def cleanup_orphaned_sessions():
    """
    Clean up sessions that never started (stuck in "created" state).

    Sessions created more than 1 hour ago but never started are marked as cancelled.
    This handles cases where session creation succeeded but start never happened.
    """
    try:
        db = SessionLocal()
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=1)

            orphaned_sessions = db.query(TestSession).filter(
                TestSession.status == "created",
                TestSession.created_at < cutoff_time,
                TestSession.started_at.is_(None)
            ).all()

            if not orphaned_sessions:
                return

            logger.warning(
                f"Found {len(orphaned_sessions)} orphaned sessions (created but never started)"
            )

            for session in orphaned_sessions:
                age_hours = (datetime.now(timezone.utc) - session.created_at).total_seconds() / 3600

                logger.warning(f"Cleaning up orphaned session {session.id} (age: {age_hours:.1f}h)")

                session.status = "cancelled"
                session.failure_reason = (
                    f"Session cancelled - created {age_hours:.1f} hours ago but never started"
                )
                session.failed_at = datetime.now(timezone.utc)
                session.failure_details = {
                    'error_type': 'orphaned_session',
                    'age_hours': age_hours,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'recoverable': False,
                    'cleanup_reason': 'automatic_orphan_cleanup'
                }

            db.commit()

            logger.info(f"Cleanup complete: cancelled {len(orphaned_sessions)} orphaned sessions")

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error during orphaned session cleanup: {e}", exc_info=True)

# Global scheduler instance
_scheduler = None

def start_cleanup_scheduler():
    """
    Start the background scheduler for session cleanup.

    This should be called once when the application starts.
    """
    global _scheduler

    if _scheduler is not None:
        logger.warning("Cleanup scheduler already running")
        return

    _scheduler = BackgroundScheduler()

    # Add stale session cleanup job
    _scheduler.add_job(
        cleanup_stale_sessions,
        trigger=IntervalTrigger(hours=CLEANUP_INTERVAL_HOURS),
        id='cleanup_stale_sessions',
        name='Cleanup stale test sessions',
        replace_existing=True
    )

    # Add orphaned session cleanup job
    _scheduler.add_job(
        cleanup_orphaned_sessions,
        trigger=IntervalTrigger(hours=CLEANUP_INTERVAL_HOURS),
        id='cleanup_orphaned_sessions',
        name='Cleanup orphaned test sessions',
        replace_existing=True
    )

    _scheduler.start()

    logger.info(
        f"Session cleanup scheduler started "
        f"(stale timeout: {STALE_SESSION_TIMEOUT_HOURS}h, "
        f"cleanup interval: {CLEANUP_INTERVAL_HOURS}h)"
    )

def stop_cleanup_scheduler():
    """Stop the cleanup scheduler (for shutdown)."""
    global _scheduler

    if _scheduler is not None:
        _scheduler.shutdown()
        _scheduler = None
        logger.info("Session cleanup scheduler stopped")

# Convenience function for manual cleanup
def run_cleanup_now():
    """
    Run cleanup jobs immediately (for testing or manual triggers).
    """
    logger.info("Running manual session cleanup")
    cleanup_stale_sessions()
    cleanup_orphaned_sessions()
