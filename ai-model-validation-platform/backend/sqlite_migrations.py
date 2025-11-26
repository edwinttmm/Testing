"""
SQLite one-time migrations to align schema with current ORM expectations.

Currently adds missing columns to the test_sessions table that are referenced by
the application but may be missing in older SQLite databases.
"""

from typing import Dict, List
from sqlalchemy.engine import Engine
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)


def _get_table_columns(engine: Engine, table: str) -> List[str]:
    with engine.connect() as conn:
        res = conn.execute(text(f"PRAGMA table_info('{table}')"))
        cols = [row[1] for row in res]  # row[1] is column name
        return cols


def ensure_test_sessions_columns(engine: Engine) -> Dict[str, str]:
    """Ensure required columns exist on test_sessions (SQLite only).

    Returns a dict of {column_name: status}, where status is 'added' or 'exists'.
    """
    try:
        if engine.dialect.name != 'sqlite':
            return {}

        existing = set(_get_table_columns(engine, 'test_sessions'))

        # Desired columns with SQLite types and sensible defaults
        desired = {
            'precision_timing_enabled': 'INTEGER DEFAULT 0',
            'timing_accuracy_ns': 'REAL',
            'drift_compensation_active': 'INTEGER DEFAULT 0',
            'frame_sync_enabled': 'INTEGER DEFAULT 0',
            'sync_point_id': 'TEXT',
            'calibration_timestamp': 'TEXT',  # ISO datetime as TEXT
            'timing_validation_status': 'TEXT',
            'hil_compliance_verified': 'INTEGER DEFAULT 0',
            'timing_degraded': 'INTEGER DEFAULT 0',
            'timing_verified': 'INTEGER DEFAULT 0',
        }

        results: Dict[str, str] = {}
        with engine.connect() as conn:
            for col, ddl in desired.items():
                if col not in existing:
                    try:
                        conn.execute(text(f"ALTER TABLE test_sessions ADD COLUMN {col} {ddl}"))
                        results[col] = 'added'
                        logger.info(f"SQLite migration: added column test_sessions.{col} {ddl}")
                    except Exception as e:
                        logger.warning(f"SQLite migration: failed to add {col}: {e}")
                else:
                    results[col] = 'exists'

        return results
    except Exception as e:
        logger.error(f"SQLite migration failed: {e}")
        return {"error": str(e)}


def ensure_detection_events_columns(engine: Engine) -> Dict[str, str]:
    """Ensure required columns exist on detection_events (SQLite only).

    This aligns legacy SQLite databases with the current ORM model fields used
    by the frontend timing workflows (ns-precision fields, etc.).

    Returns a dict of {column_name: status}, where status is 'added' or 'exists'.
    """
    try:
        if engine.dialect.name != 'sqlite':
            return {}

        existing = set(_get_table_columns(engine, 'detection_events'))

        # Desired columns and their SQLite types matching models.py
        desired = {
            # Nanosecond-precision timing fields stored as TEXT for precision
            'latency_ns': 'TEXT',
            'labjack_timestamp_ns': 'TEXT',
            'video_start_time_ns': 'TEXT',
            'monotonic_timestamp_ns': 'TEXT',
            # Accuracy metric
            'timing_accuracy_ns': 'REAL',
        }

        results: Dict[str, str] = {}
        with engine.connect() as conn:
            for col, ddl in desired.items():
                if col not in existing:
                    try:
                        conn.execute(text(f"ALTER TABLE detection_events ADD COLUMN {col} {ddl}"))
                        results[col] = 'added'
                        logger.info(f"SQLite migration: added column detection_events.{col} {ddl}")
                    except Exception as e:
                        logger.warning(f"SQLite migration: failed to add detection_events.{col}: {e}")
                else:
                    results[col] = 'exists'

        return results
    except Exception as e:
        logger.error(f"SQLite migration for detection_events failed: {e}")
        return {"error": str(e)}


def ensure_videos_columns(engine: Engine) -> Dict[str, str]:
    """Ensure required columns exist on videos (SQLite only).

    Adds validation-related columns used by the validation endpoints
    to avoid runtime SQL errors on legacy SQLite databases.
    """
    try:
        if engine.dialect.name != 'sqlite':
            return {}

        existing = set(_get_table_columns(engine, 'videos'))

        desired = {
            # Unified validation workflow fields
            'validation_status': 'TEXT DEFAULT "pending"',
            'validation_type': 'TEXT',
            'validated_at': 'TEXT',  # store ISO datetime as TEXT in SQLite
            # Legacy compatibility field frequently referenced
            'processing_status': 'TEXT DEFAULT "pending"',
        }

        results: Dict[str, str] = {}
        with engine.connect() as conn:
            for col, ddl in desired.items():
                if col not in existing:
                    try:
                        conn.execute(text(f"ALTER TABLE videos ADD COLUMN {col} {ddl}"))
                        results[col] = 'added'
                        logger.info(f"SQLite migration: added column videos.{col} {ddl}")
                    except Exception as e:
                        logger.warning(f"SQLite migration: failed to add videos.{col}: {e}")
                else:
                    results[col] = 'exists'

        return results
    except Exception as e:
        logger.error(f"SQLite migration for videos failed: {e}")
        return {"error": str(e)}
