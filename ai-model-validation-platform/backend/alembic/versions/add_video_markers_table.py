"""Add video_markers table for continuous monitoring

Revision ID: add_video_markers
Revises: add_usable_validation
Create Date: 2025-11-20

This migration adds a dedicated video_markers table to track VIDEO_START and VIDEO_END
events for multi-video test sequences. This enables precise detection segmentation and
eliminates ambiguity between "video ended" and "monitoring stopped" scenarios.

Key Features:
- Separate table for clean data separation
- Strong data integrity with foreign keys and constraints
- Optimized indexes for fast video segmentation queries
- Trigger validation for marker order (VIDEO_END must be after VIDEO_START)
- Automatic backfill from existing test_sessions and sequence_video_results
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = 'add_video_markers'
down_revision = 'add_usable_validation'
branch_labels = None
depends_on = None


def upgrade():
    """Create video_markers table with comprehensive constraints and indexes"""

    # Create video_markers table
    op.create_table(
        'video_markers',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('test_session_id', sa.String(36), sa.ForeignKey('test_sessions.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('video_id', sa.String(36), sa.ForeignKey('videos.id', ondelete='CASCADE'),
                  nullable=False),

        # Marker identification
        sa.Column('marker_type', sa.String(20), nullable=False),
        sa.Column('video_index', sa.Integer, nullable=False),

        # Timing information
        sa.Column('timestamp', sa.Float, nullable=False),
        sa.Column('timestamp_ns', sa.String(50), nullable=True),
        sa.Column('browser_timestamp', sa.Float, nullable=True),

        # Video metadata
        sa.Column('video_duration', sa.Float, nullable=True),
        sa.Column('actual_play_duration', sa.Float, nullable=True),

        # Presentation delay (T1-T0)
        sa.Column('presentation_delay_ms', sa.Float, nullable=True),

        # Quality tracking
        sa.Column('timing_quality', sa.String(20), server_default='unknown'),

        # Metadata
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('metadata', JSONB, nullable=True),

        # Constraints
        sa.CheckConstraint("marker_type IN ('VIDEO_START', 'VIDEO_END')", name='ck_marker_type'),
        sa.CheckConstraint("timing_quality IN ('high', 'medium', 'low', 'unknown')", name='ck_timing_quality'),
    )

    # Create indexes for query performance
    op.create_index('idx_video_markers_session', 'video_markers', ['test_session_id'])
    op.create_index('idx_video_markers_session_video', 'video_markers', ['test_session_id', 'video_id'])
    op.create_index('idx_video_markers_session_index', 'video_markers', ['test_session_id', 'video_index'])
    op.create_index('idx_video_markers_type', 'video_markers', ['marker_type'])
    op.create_index('idx_video_markers_timestamp', 'video_markers', ['timestamp'])
    op.create_index('idx_video_markers_session_timestamp', 'video_markers', ['test_session_id', 'timestamp'])
    op.create_index('idx_video_markers_quality', 'video_markers', ['timing_quality'])

    # Unique constraint: One marker per type per video per session
    op.create_index(
        'idx_video_markers_unique',
        'video_markers',
        ['test_session_id', 'video_id', 'video_index', 'marker_type'],
        unique=True
    )

    # Create trigger function for marker order validation
    # This ensures VIDEO_END timestamp is always after VIDEO_START timestamp
    op.execute("""
        CREATE OR REPLACE FUNCTION check_video_marker_order()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.marker_type = 'VIDEO_END' THEN
                -- Check if VIDEO_START exists and has earlier timestamp
                IF EXISTS (
                    SELECT 1 FROM video_markers
                    WHERE test_session_id = NEW.test_session_id
                        AND video_index = NEW.video_index
                        AND marker_type = 'VIDEO_START'
                        AND timestamp >= NEW.timestamp
                ) THEN
                    RAISE EXCEPTION 'VIDEO_END timestamp (%) must be after VIDEO_START timestamp for video_index %',
                        NEW.timestamp, NEW.video_index;
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Create trigger
    op.execute("""
        CREATE TRIGGER validate_marker_order
        BEFORE INSERT OR UPDATE ON video_markers
        FOR EACH ROW
        EXECUTE FUNCTION check_video_marker_order();
    """)

    # Backfill markers from existing test_sessions
    # Step 1: Single-video sessions (non-sequence sessions)
    print("Backfilling markers from single-video test sessions...")
    op.execute("""
        INSERT INTO video_markers (
            id,
            test_session_id,
            video_id,
            marker_type,
            video_index,
            timestamp,
            timestamp_ns,
            presentation_delay_ms,
            timing_quality
        )
        SELECT
            gen_random_uuid()::text,
            ts.id,
            ts.video_id,
            'VIDEO_START',
            0,  -- Single video = index 0
            ts.video_playback_start_time,
            ts.video_playback_start_time_ns,
            ts.presentation_delay_ms,
            CASE
                WHEN ts.timing_degraded THEN 'low'
                WHEN ts.timing_verified THEN 'high'
                ELSE 'medium'
            END
        FROM test_sessions ts
        WHERE ts.video_playback_start_time IS NOT NULL
          AND (ts.has_video_sequence = FALSE OR ts.has_video_sequence IS NULL)
          AND ts.video_id IS NOT NULL;
    """)

    # Step 2: Multi-video sessions - VIDEO_START markers from sequence_video_results
    print("Backfilling VIDEO_START markers from multi-video sequences...")
    op.execute("""
        INSERT INTO video_markers (
            id,
            test_session_id,
            video_id,
            marker_type,
            video_index,
            timestamp,
            timestamp_ns,
            actual_play_duration,
            presentation_delay_ms,
            timing_quality
        )
        SELECT
            gen_random_uuid()::text,
            vts.test_session_id,
            svr.video_id,
            'VIDEO_START',
            svr.sequence_order,
            svr.video_start_time,
            svr.video_start_time_ns,
            svr.actual_duration_ms / 1000.0,  -- Convert to seconds
            svr.frontend_playing_delay_ms,
            CASE
                WHEN svr.video_status = 'completed' THEN 'high'
                WHEN svr.video_status = 'failed' THEN 'low'
                ELSE 'medium'
            END
        FROM sequence_video_results svr
        JOIN video_test_sequences vts ON svr.video_sequence_id = vts.id
        WHERE svr.video_start_time IS NOT NULL
          AND svr.video_id IS NOT NULL;
    """)

    # Step 3: Multi-video sessions - VIDEO_END markers from sequence_video_results
    print("Backfilling VIDEO_END markers from multi-video sequences...")
    op.execute("""
        INSERT INTO video_markers (
            id,
            test_session_id,
            video_id,
            marker_type,
            video_index,
            timestamp,
            timestamp_ns,
            actual_play_duration,
            timing_quality
        )
        SELECT
            gen_random_uuid()::text,
            vts.test_session_id,
            svr.video_id,
            'VIDEO_END',
            svr.sequence_order,
            svr.video_end_time,
            svr.video_end_time_ns,
            svr.actual_duration_ms / 1000.0,  -- Convert to seconds
            CASE
                WHEN svr.video_status = 'completed' THEN 'high'
                WHEN svr.video_status = 'failed' THEN 'low'
                ELSE 'medium'
            END
        FROM sequence_video_results svr
        JOIN video_test_sequences vts ON svr.video_sequence_id = vts.id
        WHERE svr.video_end_time IS NOT NULL
          AND svr.video_id IS NOT NULL;
    """)

    # Validation: Check marker integrity after backfill
    print("Validating backfilled markers...")
    op.execute("""
        DO $$
        DECLARE
            orphaned_markers INT;
            invalid_order_count INT;
            missing_start_count INT;
            missing_end_count INT;
        BEGIN
            -- Check for orphaned markers (shouldn't happen due to foreign keys)
            SELECT COUNT(*) INTO orphaned_markers
            FROM video_markers vm
            LEFT JOIN test_sessions ts ON vm.test_session_id = ts.id
            WHERE ts.id IS NULL;

            IF orphaned_markers > 0 THEN
                RAISE WARNING 'Found % orphaned markers (invalid test_session_id)', orphaned_markers;
            END IF;

            -- Check for VIDEO_END before VIDEO_START
            SELECT COUNT(*) INTO invalid_order_count
            FROM (
                SELECT
                    test_session_id,
                    video_index,
                    MAX(CASE WHEN marker_type = 'VIDEO_START' THEN timestamp END) as start_time,
                    MAX(CASE WHEN marker_type = 'VIDEO_END' THEN timestamp END) as end_time
                FROM video_markers
                GROUP BY test_session_id, video_index
            ) bounds
            WHERE end_time < start_time;

            IF invalid_order_count > 0 THEN
                RAISE WARNING 'Found % videos with VIDEO_END before VIDEO_START', invalid_order_count;
            END IF;

            -- Check for videos with only START marker (no END)
            SELECT COUNT(*) INTO missing_end_count
            FROM (
                SELECT
                    test_session_id,
                    video_index,
                    COUNT(CASE WHEN marker_type = 'VIDEO_START' THEN 1 END) as start_count,
                    COUNT(CASE WHEN marker_type = 'VIDEO_END' THEN 1 END) as end_count
                FROM video_markers
                GROUP BY test_session_id, video_index
            ) counts
            WHERE start_count > 0 AND end_count = 0;

            IF missing_end_count > 0 THEN
                RAISE WARNING 'Found % videos with VIDEO_START but no VIDEO_END (incomplete sessions)', missing_end_count;
            END IF;

            -- Check for videos with only END marker (no START)
            SELECT COUNT(*) INTO missing_start_count
            FROM (
                SELECT
                    test_session_id,
                    video_index,
                    COUNT(CASE WHEN marker_type = 'VIDEO_START' THEN 1 END) as start_count,
                    COUNT(CASE WHEN marker_type = 'VIDEO_END' THEN 1 END) as end_count
                FROM video_markers
                GROUP BY test_session_id, video_index
            ) counts
            WHERE start_count = 0 AND end_count > 0;

            IF missing_start_count > 0 THEN
                RAISE WARNING 'Found % videos with VIDEO_END but no VIDEO_START (data corruption?)', missing_start_count;
            END IF;

            RAISE NOTICE 'Marker validation complete. Total markers: %', (SELECT COUNT(*) FROM video_markers);
        END $$;
    """)


def downgrade():
    """Remove video_markers table and related objects"""

    # Drop trigger and function
    op.execute("DROP TRIGGER IF EXISTS validate_marker_order ON video_markers;")
    op.execute("DROP FUNCTION IF EXISTS check_video_marker_order();")

    # Drop indexes (most will be dropped automatically with table, but explicit is safer)
    op.drop_index('idx_video_markers_unique', table_name='video_markers')
    op.drop_index('idx_video_markers_quality', table_name='video_markers')
    op.drop_index('idx_video_markers_session_timestamp', table_name='video_markers')
    op.drop_index('idx_video_markers_timestamp', table_name='video_markers')
    op.drop_index('idx_video_markers_type', table_name='video_markers')
    op.drop_index('idx_video_markers_session_index', table_name='video_markers')
    op.drop_index('idx_video_markers_session_video', table_name='video_markers')
    op.drop_index('idx_video_markers_session', table_name='video_markers')

    # Drop table (CASCADE will handle foreign keys)
    op.drop_table('video_markers')

    print("video_markers table and related objects removed successfully")
