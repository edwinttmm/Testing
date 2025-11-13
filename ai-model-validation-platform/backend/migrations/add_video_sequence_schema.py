"""
Multi-Video Sequential Testing Schema Migration

This migration adds support for sequential multi-video testing with:
1. VideoTestSequence - Container for ordered video sequences
2. SequenceVideoResult - Per-video results within sequences
3. Enhanced DetectionEvent - Video-relative timing fields
4. TestSession updates - Sequence relationship flag

Migration Version: 2025-09-30
Author: Backend API Developer Agent
"""

import logging
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, ForeignKey,
    JSON, Index, text, inspect
)
from sqlalchemy.sql import func
from sqlalchemy.exc import OperationalError, ProgrammingError
from database import engine, Base
import uuid

logger = logging.getLogger(__name__)

# Migration version tracking
MIGRATION_VERSION = "add_video_sequence_schema_v1"

def check_column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table"""
    try:
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception as e:
        logger.warning(f"Could not inspect table {table_name}: {e}")
        return False

def check_table_exists(table_name: str) -> bool:
    """Check if a table exists"""
    try:
        inspector = inspect(engine)
        return table_name in inspector.get_table_names()
    except Exception as e:
        logger.warning(f"Could not check if table {table_name} exists: {e}")
        return False

def add_column_safe(conn, table_name: str, column_name: str, column_def: str):
    """Safely add a column if it doesn't exist"""
    if not check_column_exists(table_name, column_name):
        try:
            conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}"))
            logger.info(f"✅ Added column {table_name}.{column_name}")
            return True
        except (OperationalError, ProgrammingError) as e:
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                logger.info(f"Column {table_name}.{column_name} already exists (safe)")
                return False
            raise
    else:
        logger.info(f"Column {table_name}.{column_name} already exists")
        return False

def create_index_safe(conn, index_name: str, table_name: str, columns: list):
    """Safely create an index if it doesn't exist"""
    columns_str = ", ".join(columns)
    try:
        conn.execute(text(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({columns_str})"))
        logger.info(f"✅ Created index {index_name}")
        return True
    except (OperationalError, ProgrammingError) as e:
        if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
            logger.info(f"Index {index_name} already exists (safe)")
            return False
        raise

def upgrade_test_sessions():
    """Add video sequence support to test_sessions table"""
    logger.info("📝 Upgrading test_sessions table for video sequences...")

    with engine.begin() as conn:
        # Add has_video_sequence flag
        add_column_safe(
            conn,
            "test_sessions",
            "has_video_sequence",
            "BOOLEAN DEFAULT FALSE"
        )

        # Add index for sequence filtering
        create_index_safe(
            conn,
            "idx_testsession_sequence_flag",
            "test_sessions",
            ["has_video_sequence", "status"]
        )

    logger.info("✅ test_sessions table upgraded")

def create_video_test_sequences():
    """Create video_test_sequences table"""
    logger.info("📝 Creating video_test_sequences table...")

    if check_table_exists("video_test_sequences"):
        logger.info("Table video_test_sequences already exists")
        return

    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS video_test_sequences (
                id VARCHAR(36) PRIMARY KEY,
                test_session_id VARCHAR(36) NOT NULL,
                name VARCHAR(255) NOT NULL,
                video_ids JSON NOT NULL,
                sequence_order JSON NOT NULL,
                status VARCHAR(50) DEFAULT 'pending',
                max_latency_ms INTEGER DEFAULT 100,
                sequence_start_time FLOAT,
                sequence_start_time_ns VARCHAR(50),
                sequence_end_time FLOAT,
                sequence_end_time_ns VARCHAR(50),
                total_duration_ms FLOAT,
                current_video_index INTEGER DEFAULT 0,
                total_videos INTEGER NOT NULL,
                completed_videos INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                FOREIGN KEY (test_session_id) REFERENCES test_sessions(id) ON DELETE CASCADE
            )
        """))

        # Create indexes for performance
        indexes = [
            ("idx_video_seq_session", ["test_session_id"]),
            ("idx_video_seq_status", ["status"]),
            ("idx_video_seq_session_status", ["test_session_id", "status"]),
            ("idx_video_seq_created", ["created_at"]),
            ("idx_video_seq_progress", ["current_video_index", "total_videos"]),
            ("idx_video_seq_timing", ["sequence_start_time"]),
        ]

        for idx_name, columns in indexes:
            create_index_safe(conn, idx_name, "video_test_sequences", columns)

    logger.info("✅ video_test_sequences table created")

def create_sequence_video_results():
    """Create sequence_video_results table"""
    logger.info("📝 Creating sequence_video_results table...")

    if check_table_exists("sequence_video_results"):
        logger.info("Table sequence_video_results already exists")
        return

    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS sequence_video_results (
                id VARCHAR(36) PRIMARY KEY,
                video_sequence_id VARCHAR(36) NOT NULL,
                video_id VARCHAR(36) NOT NULL,
                sequence_order INTEGER NOT NULL,
                video_start_time FLOAT,
                video_start_time_ns VARCHAR(50),
                video_end_time FLOAT,
                video_end_time_ns VARCHAR(50),
                actual_duration_ms FLOAT,
                video_play_offset_ms FLOAT,
                video_status VARCHAR(50) DEFAULT 'pending',
                validation_result VARCHAR(50),
                expected_detection_count INTEGER DEFAULT 0,
                actual_detection_count INTEGER DEFAULT 0,
                passed_detections INTEGER DEFAULT 0,
                failed_detections INTEGER DEFAULT 0,
                avg_latency_ms FLOAT,
                max_latency_ms FLOAT,
                min_latency_ms FLOAT,
                pass_rate_percent FLOAT,
                latency_threshold_ms INTEGER,
                processing_time_ms FLOAT,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                FOREIGN KEY (video_sequence_id) REFERENCES video_test_sequences(id) ON DELETE CASCADE,
                FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
            )
        """))

        # Create indexes for performance
        indexes = [
            ("idx_seq_video_result_sequence", ["video_sequence_id"]),
            ("idx_seq_video_result_video", ["video_id"]),
            ("idx_seq_video_result_order", ["video_sequence_id", "sequence_order"]),
            ("idx_seq_video_result_status", ["video_status"]),
            ("idx_seq_video_result_validation", ["validation_result"]),
            ("idx_seq_video_result_latency", ["avg_latency_ms"]),
            ("idx_seq_video_result_pass_rate", ["pass_rate_percent"]),
            ("idx_seq_video_result_timing", ["video_start_time"]),
            ("idx_seq_video_result_sequence_status", ["video_sequence_id", "video_status"]),
            ("idx_seq_video_result_detection_counts", ["expected_detection_count", "actual_detection_count"]),
        ]

        for idx_name, columns in indexes:
            create_index_safe(conn, idx_name, "sequence_video_results", columns)

    logger.info("✅ sequence_video_results table created")

def upgrade_detection_events():
    """Add sequence and video-relative fields to detection_events"""
    logger.info("📝 Upgrading detection_events table for sequence support...")

    with engine.begin() as conn:
        # Add sequence_video_result relationship
        add_column_safe(
            conn,
            "detection_events",
            "sequence_video_result_id",
            "VARCHAR(36)"
        )

        # Add video-relative timing fields (if not already present)
        timing_fields = [
            ("video_relative_timestamp", "FLOAT"),
            ("video_relative_timestamp_ns", "VARCHAR(50)"),
            ("sequence_timestamp", "FLOAT"),
            ("sequence_timestamp_ns", "VARCHAR(50)"),
            ("video_play_offset_ms", "FLOAT"),
        ]

        for field_name, field_type in timing_fields:
            add_column_safe(conn, "detection_events", field_name, field_type)

        # Add correlation method field
        add_column_safe(
            conn,
            "detection_events",
            "correlation_method",
            "VARCHAR(50) DEFAULT 'timestamp'"
        )

        # Create indexes for sequence queries
        indexes = [
            ("idx_detection_sequence_video_result", ["sequence_video_result_id"]),
            ("idx_detection_sequence_timestamp", ["sequence_timestamp"]),
            ("idx_detection_video_relative_timestamp", ["video_relative_timestamp"]),
            ("idx_detection_correlation_method", ["correlation_method"]),
            ("idx_detection_seq_video_validation", ["sequence_video_result_id", "validation_result"]),
            ("idx_detection_seq_video_latency", ["sequence_video_result_id", "actual_latency_ms"]),
        ]

        for idx_name, columns in indexes:
            create_index_safe(conn, idx_name, "detection_events", columns)

        # Add foreign key constraint (if database supports it)
        try:
            conn.execute(text("""
                ALTER TABLE detection_events
                ADD CONSTRAINT fk_detection_seq_video_result
                FOREIGN KEY (sequence_video_result_id)
                REFERENCES sequence_video_results(id)
                ON DELETE SET NULL
            """))
            logger.info("✅ Added foreign key constraint for sequence_video_result_id")
        except (OperationalError, ProgrammingError) as e:
            if "already exists" not in str(e).lower():
                logger.warning(f"Could not add foreign key (may not be supported): {e}")

    logger.info("✅ detection_events table upgraded")

def verify_migration():
    """Verify migration completed successfully"""
    logger.info("🔍 Verifying migration...")

    inspector = inspect(engine)

    # Check tables exist
    required_tables = ["video_test_sequences", "sequence_video_results"]
    for table in required_tables:
        if not check_table_exists(table):
            raise Exception(f"Migration failed: table {table} not created")

    # Check test_sessions has_video_sequence column
    if not check_column_exists("test_sessions", "has_video_sequence"):
        raise Exception("Migration failed: test_sessions.has_video_sequence not added")

    # Check detection_events has sequence fields
    required_columns = [
        "sequence_video_result_id",
        "sequence_timestamp",
        "correlation_method"
    ]
    for column in required_columns:
        if not check_column_exists("detection_events", column):
            raise Exception(f"Migration failed: detection_events.{column} not added")

    logger.info("✅ Migration verification passed")

def run_migration():
    """Execute the complete migration"""
    logger.info("="*70)
    logger.info("🚀 Starting Multi-Video Sequential Testing Schema Migration")
    logger.info("="*70)

    try:
        # Step 1: Upgrade existing tables
        upgrade_test_sessions()
        upgrade_detection_events()

        # Step 2: Create new tables
        create_video_test_sequences()
        create_sequence_video_results()

        # Step 3: Verify migration
        verify_migration()

        logger.info("="*70)
        logger.info("✅ Multi-Video Sequential Testing Schema Migration Completed Successfully")
        logger.info("="*70)

        return True

    except Exception as e:
        logger.error("="*70)
        logger.error(f"❌ Migration failed: {str(e)}")
        logger.error("="*70)
        raise

def rollback_migration():
    """Rollback migration changes"""
    logger.warning("="*70)
    logger.warning("🔄 Rolling back Multi-Video Sequential Testing Schema Migration")
    logger.warning("="*70)

    try:
        with engine.begin() as conn:
            # Drop new tables
            conn.execute(text("DROP TABLE IF EXISTS sequence_video_results"))
            conn.execute(text("DROP TABLE IF EXISTS video_test_sequences"))

            # Remove columns from detection_events
            if check_column_exists("detection_events", "sequence_video_result_id"):
                conn.execute(text("ALTER TABLE detection_events DROP COLUMN sequence_video_result_id"))

            # Remove column from test_sessions
            if check_column_exists("test_sessions", "has_video_sequence"):
                conn.execute(text("ALTER TABLE test_sessions DROP COLUMN has_video_sequence"))

        logger.warning("✅ Rollback completed")

    except Exception as e:
        logger.error(f"❌ Rollback failed: {str(e)}")
        raise

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        rollback_migration()
    else:
        run_migration()
