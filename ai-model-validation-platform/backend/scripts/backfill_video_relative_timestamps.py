"""
Utility script to backfill detection_events.video_relative_timestamp values so that
stored detections use per-video relative time instead of sequence-relative time.

Usage:
    python -m scripts.backfill_video_relative_timestamps          # backfill all sessions
    python -m scripts.backfill_video_relative_timestamps SESSION  # backfill single session
"""

import logging
import sys
from typing import Optional

from sqlalchemy.orm import Session

from database import SessionLocal
from models import DetectionEvent

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def _backfill_for_session(db: Session, session_id: Optional[str] = None) -> int:
    """
    Adjust video_relative_timestamp using sequence_timestamp - video_play_offset_ms/1000.
    Returns number of rows updated.
    """
    query = db.query(DetectionEvent).filter(
        DetectionEvent.sequence_timestamp.isnot(None),
        DetectionEvent.video_play_offset_ms.isnot(None),
    )

    if session_id:
        query = query.filter(DetectionEvent.test_session_id == session_id)

    updated = 0

    for event in query.yield_per(500):
        adjusted = event.sequence_timestamp - (event.video_play_offset_ms or 0.0) / 1000.0

        if adjusted is None:
            continue

        if adjusted < -0.05:
            logger.debug(
                "Event %s (session %s) produced negative adjusted time %.3f – clamping to 0.0",
                event.id,
                event.test_session_id,
                adjusted,
            )
            adjusted = 0.0
        else:
            adjusted = max(adjusted, 0.0)

        event.video_relative_timestamp = adjusted

        if event.video_frame_number is None:
            # Default to 24fps when frame rate metadata is unavailable
            event.video_frame_number = int(round(adjusted * 24.0))

        updated += 1

    db.commit()
    return updated


def main(session_id: Optional[str] = None) -> None:
    db = SessionLocal()
    try:
        count = _backfill_for_session(db, session_id=session_id)
        scope = session_id or "ALL sessions"
        logger.info("Updated %s detection events for %s", count, scope)
    finally:
        db.close()


if __name__ == "__main__":
    sid = sys.argv[1] if len(sys.argv) > 1 else None
    main(sid)
