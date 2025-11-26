"""Add video lifecycle tracking for drift calculation

Revision ID: f18f8e9c1590
Revises: add_video_markers
Create Date: 2025-11-20

This migration adds comprehensive video lifecycle event tracking for precise drift calculation
in HIL testing. It introduces a dedicated table for VIDEO_START, VIDEO_END, and VIDEO_ERROR
events, along with drift compensation fields for detection events.

Key Features:
- video_lifecycle_events table for per-video start/end tracking
- Browser-to-backend timestamp synchronization (clock_offset_ms)
- LabJack command timing integration for drift calculation
- Drift-compensated timestamps for detection_events
- Average drift tracking at test_session level
- Production-grade constraints and indexes for performance

Design Documentation: /backend/docs/VIDEO_MARKERS_SCHEMA_DESIGN.md
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = 'f18f8e9c1590'
down_revision = 'add_video_markers'
branch_labels = None
depends_on = None


def upgrade():
    """Create video_lifecycle_events table and add drift tracking fields"""

    # ===== STEP 1: Create video_lifecycle_events table =====
    print("Creating video_lifecycle_events table...")

    op.create_table(
        'video_lifecycle_events',
        # Primary key
        sa.Column('id', sa.String(36), primary_key=True),

        # Foreign keys
        sa.Column('test_session_id', sa.String(36),
                  sa.ForeignKey('test_sessions.id', ondelete='CASCADE'),
                  nullable=False, index=True,
                  comment='FK to test_sessions - CASCADE delete for cleanup'),
        sa.Column('video_id', sa.String(36),
                  sa.ForeignKey('videos.id', ondelete='CASCADE'),
                  nullable=False, index=True,
                  comment='FK to videos - CASCADE delete for cleanup'),

        # Event identification
        sa.Column('event_type', sa.String(20), nullable=False, index=True,
                  comment='Event type: VIDEO_START, VIDEO_END, VIDEO_ERROR'),

        # Timestamp chain for drift calculation
        sa.Column('frontend_timestamp', sa.Float, nullable=False,
                  comment='Browser performance.now() timestamp when event occurred'),
        sa.Column('backend_received_timestamp', sa.Float, nullable=False,
                  comment='Backend server timestamp when event was received'),
        sa.Column('labjack_command_sent_timestamp', sa.Float, nullable=True,
                  comment='Timestamp when LabJack command was sent (T0 for VIDEO_START)'),
        sa.Column('labjack_monitoring_timestamp', sa.Float, nullable=True,
                  comment='Timestamp when LabJack confirmed monitoring started (T1)'),

        # Clock synchronization
        sa.Column('clock_offset_ms', sa.Float, nullable=True,
                  comment='Browser-backend clock offset in milliseconds (for drift calculation)'),

        # Calculated drift
        sa.Column('calculated_drift_ms', sa.Float, nullable=True,
                  comment='Total calculated drift for this video lifecycle (ms)'),

        # Additional metadata (named 'event_metadata' to avoid SQLAlchemy reserved 'metadata')
        sa.Column('event_metadata', JSONB, nullable=True,
                  comment='Additional event context (browser info, video metadata, etc.)'),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('NOW()'), nullable=False,
                  comment='Database record creation timestamp'),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  onupdate=sa.text('NOW()'),
                  comment='Database record update timestamp'),

        # Constraints
        sa.CheckConstraint(
            "event_type IN ('VIDEO_START', 'VIDEO_END', 'VIDEO_ERROR')",
            name='ck_lifecycle_event_type'
        ),
        sa.CheckConstraint(
            "calculated_drift_ms IS NULL OR (calculated_drift_ms >= -1000 AND calculated_drift_ms <= 1000)",
            name='ck_lifecycle_drift_range',
            comment='Drift must be within ±1000ms for sanity checking'
        ),

        # Table comment
        comment='Tracks video lifecycle events (START/END/ERROR) with precise timestamps for drift calculation'
    )

    # ===== STEP 2: Create indexes for performance =====
    print("Creating indexes for video_lifecycle_events...")

    # Primary query indexes
    op.create_index(
        'idx_lifecycle_session_event_created',
        'video_lifecycle_events',
        ['test_session_id', 'event_type', 'created_at'],
        comment='Composite index for session-based queries with temporal ordering'
    )

    op.create_index(
        'idx_lifecycle_video_event',
        'video_lifecycle_events',
        ['video_id', 'event_type'],
        comment='Per-video event queries'
    )

    op.create_index(
        'idx_lifecycle_drift',
        'video_lifecycle_events',
        ['calculated_drift_ms'],
        postgresql_where=sa.text("calculated_drift_ms IS NOT NULL"),
        comment='Drift analysis queries (partial index for non-null values)'
    )

    # Unique constraint: One event per type per video per session
    op.create_index(
        'idx_lifecycle_unique_event',
        'video_lifecycle_events',
        ['test_session_id', 'video_id', 'event_type'],
        unique=True,
        comment='Ensure only one START/END/ERROR event per video in a session'
    )

    # ===== STEP 3: Add columns to detection_events =====
    print("Adding drift compensation columns to detection_events...")

    op.add_column('detection_events',
        sa.Column('drift_compensated_timestamp', sa.Float, nullable=True,
                  comment='Drift-compensated timestamp (original_timestamp + calculated_drift_ms)')
    )

    op.add_column('detection_events',
        sa.Column('original_timestamp', sa.Float, nullable=True,
                  comment='Original timestamp before drift compensation (preserved for debugging)')
    )

    # Create index for drift-compensated queries
    op.create_index(
        'idx_detection_drift_timestamp',
        'detection_events',
        ['test_session_id', 'drift_compensated_timestamp'],
        postgresql_where=sa.text("drift_compensated_timestamp IS NOT NULL"),
        comment='Drift-compensated temporal queries'
    )

    # ===== STEP 4: Add column to test_sessions =====
    print("Adding average drift tracking to test_sessions...")

    op.add_column('test_sessions',
        sa.Column('average_drift_ms', sa.Float, nullable=True,
                  comment='Average drift across all videos in this session (for reporting)')
    )

    # Create index for drift analysis
    op.create_index(
        'idx_session_average_drift',
        'test_sessions',
        ['average_drift_ms'],
        postgresql_where=sa.text("average_drift_ms IS NOT NULL"),
        comment='Session-level drift analysis'
    )

    # ===== STEP 5: Backfill original_timestamp from existing timestamp =====
    print("Backfilling original_timestamp for existing detection_events...")

    op.execute("""
        UPDATE detection_events
        SET original_timestamp = timestamp
        WHERE timestamp IS NOT NULL
          AND original_timestamp IS NULL
    """)

    # ===== STEP 6: Create trigger for automatic drift calculation =====
    print("Creating trigger for automatic drift calculation...")

    # Trigger function to calculate drift when VIDEO_END is inserted
    op.execute("""
        CREATE OR REPLACE FUNCTION calculate_video_drift()
        RETURNS TRIGGER AS $$
        DECLARE
            start_event RECORD;
            calculated_drift FLOAT;
        BEGIN
            -- Only calculate drift for VIDEO_END events
            IF NEW.event_type = 'VIDEO_END' THEN
                -- Find corresponding VIDEO_START event
                SELECT * INTO start_event
                FROM video_lifecycle_events
                WHERE test_session_id = NEW.test_session_id
                  AND video_id = NEW.video_id
                  AND event_type = 'VIDEO_START'
                LIMIT 1;

                IF FOUND THEN
                    -- Calculate drift: (backend_received - frontend) difference between END and START
                    -- This captures cumulative drift over video lifecycle
                    calculated_drift :=
                        (NEW.backend_received_timestamp - NEW.frontend_timestamp) -
                        (start_event.backend_received_timestamp - start_event.frontend_timestamp);

                    -- Update the VIDEO_END event with calculated drift
                    NEW.calculated_drift_ms := calculated_drift;

                    RAISE NOTICE 'Calculated drift for video % in session %: % ms',
                        NEW.video_id, NEW.test_session_id, calculated_drift;
                ELSE
                    RAISE WARNING 'No VIDEO_START found for video % in session % - cannot calculate drift',
                        NEW.video_id, NEW.test_session_id;
                END IF;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        COMMENT ON FUNCTION calculate_video_drift() IS
        'Automatically calculates drift when VIDEO_END event is inserted by comparing with VIDEO_START';
    """)

    # Create trigger
    op.execute("""
        CREATE TRIGGER trigger_calculate_video_drift
        BEFORE INSERT OR UPDATE ON video_lifecycle_events
        FOR EACH ROW
        EXECUTE FUNCTION calculate_video_drift();
    """)

    # ===== STEP 7: Create view for easy drift querying =====
    print("Creating video_drift_summary view...")

    op.execute("""
        CREATE OR REPLACE VIEW video_drift_summary AS
        SELECT
            ts.id as test_session_id,
            ts.name as session_name,
            v.id as video_id,
            v.filename as video_filename,
            vle_start.frontend_timestamp as video_start_frontend_ts,
            vle_start.backend_received_timestamp as video_start_backend_ts,
            vle_start.labjack_monitoring_timestamp as video_start_labjack_ts,
            vle_end.frontend_timestamp as video_end_frontend_ts,
            vle_end.backend_received_timestamp as video_end_backend_ts,
            vle_end.calculated_drift_ms as drift_ms,
            vle_end.clock_offset_ms as clock_offset_ms,
            CASE
                WHEN vle_end.calculated_drift_ms IS NULL THEN 'NO_DATA'
                WHEN ABS(vle_end.calculated_drift_ms) > 500 THEN 'HIGH_DRIFT'
                WHEN ABS(vle_end.calculated_drift_ms) > 100 THEN 'MODERATE_DRIFT'
                ELSE 'LOW_DRIFT'
            END as drift_severity,
            vle_start.created_at as start_recorded_at,
            vle_end.created_at as end_recorded_at
        FROM test_sessions ts
        JOIN videos v ON ts.video_id = v.id OR v.id IN (
            SELECT video_id FROM video_lifecycle_events WHERE test_session_id = ts.id
        )
        LEFT JOIN video_lifecycle_events vle_start ON
            vle_start.test_session_id = ts.id
            AND vle_start.video_id = v.id
            AND vle_start.event_type = 'VIDEO_START'
        LEFT JOIN video_lifecycle_events vle_end ON
            vle_end.test_session_id = ts.id
            AND vle_end.video_id = v.id
            AND vle_end.event_type = 'VIDEO_END'
        WHERE vle_start.id IS NOT NULL OR vle_end.id IS NOT NULL;

        COMMENT ON VIEW video_drift_summary IS
        'Denormalized view for easy drift analysis across test sessions and videos';
    """)

    # ===== STEP 8: Data migration for existing sessions =====
    print("Backfilling lifecycle events from existing video_markers...")

    # Migrate VIDEO_START events from video_markers
    op.execute("""
        INSERT INTO video_lifecycle_events (
            id,
            test_session_id,
            video_id,
            event_type,
            frontend_timestamp,
            backend_received_timestamp,
            labjack_command_sent_timestamp,
            labjack_monitoring_timestamp,
            clock_offset_ms,
            calculated_drift_ms,
            event_metadata,
            created_at
        )
        SELECT
            gen_random_uuid()::text,
            vm.test_session_id,
            vm.video_id,
            'VIDEO_START',
            COALESCE(vm.browser_timestamp, vm.timestamp) as frontend_timestamp,
            vm.timestamp as backend_received_timestamp,
            NULL as labjack_command_sent_timestamp,  -- Legacy data doesn't have this
            NULL as labjack_monitoring_timestamp,     -- Legacy data doesn't have this
            0.0 as clock_offset_ms,                   -- Assume zero offset for legacy data
            0.0 as calculated_drift_ms,               -- Set to zero for existing data
            jsonb_build_object(
                'source', 'video_markers_migration',
                'presentation_delay_ms', vm.presentation_delay_ms,
                'timing_quality', vm.timing_quality,
                'video_duration', vm.video_duration,
                'video_index', vm.video_index
            ) as event_metadata,
            vm.created_at
        FROM video_markers vm
        WHERE vm.marker_type = 'VIDEO_START'
        ON CONFLICT (test_session_id, video_id, event_type) DO NOTHING;
    """)

    # Migrate VIDEO_END events from video_markers
    op.execute("""
        INSERT INTO video_lifecycle_events (
            id,
            test_session_id,
            video_id,
            event_type,
            frontend_timestamp,
            backend_received_timestamp,
            labjack_command_sent_timestamp,
            labjack_monitoring_timestamp,
            clock_offset_ms,
            calculated_drift_ms,
            event_metadata,
            created_at
        )
        SELECT
            gen_random_uuid()::text,
            vm.test_session_id,
            vm.video_id,
            'VIDEO_END',
            COALESCE(vm.browser_timestamp, vm.timestamp) as frontend_timestamp,
            vm.timestamp as backend_received_timestamp,
            NULL as labjack_command_sent_timestamp,
            NULL as labjack_monitoring_timestamp,
            0.0 as clock_offset_ms,
            0.0 as calculated_drift_ms,  -- Set to zero for existing data
            jsonb_build_object(
                'source', 'video_markers_migration',
                'timing_quality', vm.timing_quality,
                'actual_play_duration', vm.actual_play_duration,
                'video_index', vm.video_index
            ) as event_metadata,
            vm.created_at
        FROM video_markers vm
        WHERE vm.marker_type = 'VIDEO_END'
        ON CONFLICT (test_session_id, video_id, event_type) DO NOTHING;
    """)

    # ===== STEP 9: Calculate average drift for sessions =====
    print("Calculating average drift for test sessions...")

    op.execute("""
        UPDATE test_sessions ts
        SET average_drift_ms = (
            SELECT AVG(vle.calculated_drift_ms)
            FROM video_lifecycle_events vle
            WHERE vle.test_session_id = ts.id
              AND vle.event_type = 'VIDEO_END'
              AND vle.calculated_drift_ms IS NOT NULL
        )
        WHERE EXISTS (
            SELECT 1 FROM video_lifecycle_events vle
            WHERE vle.test_session_id = ts.id
              AND vle.calculated_drift_ms IS NOT NULL
        );
    """)

    # ===== STEP 10: Validation checks =====
    print("Running validation checks...")

    op.execute("""
        DO $$
        DECLARE
            total_events INT;
            start_events INT;
            end_events INT;
            error_events INT;
            sessions_with_drift INT;
            avg_drift FLOAT;
            max_drift FLOAT;
            min_drift FLOAT;
        BEGIN
            -- Count events by type
            SELECT COUNT(*) INTO total_events FROM video_lifecycle_events;
            SELECT COUNT(*) INTO start_events FROM video_lifecycle_events WHERE event_type = 'VIDEO_START';
            SELECT COUNT(*) INTO end_events FROM video_lifecycle_events WHERE event_type = 'VIDEO_END';
            SELECT COUNT(*) INTO error_events FROM video_lifecycle_events WHERE event_type = 'VIDEO_ERROR';

            -- Count sessions with calculated drift
            SELECT COUNT(DISTINCT test_session_id) INTO sessions_with_drift
            FROM video_lifecycle_events
            WHERE calculated_drift_ms IS NOT NULL;

            -- Calculate drift statistics
            SELECT AVG(calculated_drift_ms), MAX(calculated_drift_ms), MIN(calculated_drift_ms)
            INTO avg_drift, max_drift, min_drift
            FROM video_lifecycle_events
            WHERE calculated_drift_ms IS NOT NULL;

            -- Report results
            RAISE NOTICE '=== Video Lifecycle Events Migration Summary ===';
            RAISE NOTICE 'Total events created: %', total_events;
            RAISE NOTICE '  - VIDEO_START: %', start_events;
            RAISE NOTICE '  - VIDEO_END: %', end_events;
            RAISE NOTICE '  - VIDEO_ERROR: %', error_events;
            RAISE NOTICE 'Sessions with drift data: %', sessions_with_drift;

            IF avg_drift IS NOT NULL THEN
                RAISE NOTICE 'Drift statistics:';
                RAISE NOTICE '  - Average drift: % ms', ROUND(avg_drift::numeric, 2);
                RAISE NOTICE '  - Max drift: % ms', ROUND(max_drift::numeric, 2);
                RAISE NOTICE '  - Min drift: % ms', ROUND(min_drift::numeric, 2);
            END IF;

            -- Check for mismatched START/END pairs
            WITH event_counts AS (
                SELECT
                    test_session_id,
                    video_id,
                    COUNT(CASE WHEN event_type = 'VIDEO_START' THEN 1 END) as starts,
                    COUNT(CASE WHEN event_type = 'VIDEO_END' THEN 1 END) as ends
                FROM video_lifecycle_events
                GROUP BY test_session_id, video_id
            )
            SELECT COUNT(*) INTO total_events
            FROM event_counts
            WHERE starts != ends;

            IF total_events > 0 THEN
                RAISE WARNING 'Found % videos with mismatched START/END events', total_events;
            ELSE
                RAISE NOTICE 'All videos have matching START/END events';
            END IF;

            RAISE NOTICE '=== Migration completed successfully ===';
        END $$;
    """)


def downgrade():
    """Remove video lifecycle tracking features"""

    print("Rolling back video lifecycle tracking migration...")

    # Drop view
    op.execute("DROP VIEW IF EXISTS video_drift_summary;")

    # Drop trigger and function
    op.execute("DROP TRIGGER IF EXISTS trigger_calculate_video_drift ON video_lifecycle_events;")
    op.execute("DROP FUNCTION IF EXISTS calculate_video_drift();")

    # Drop indexes from test_sessions
    op.drop_index('idx_session_average_drift', table_name='test_sessions')

    # Drop column from test_sessions
    op.drop_column('test_sessions', 'average_drift_ms')

    # Drop indexes from detection_events
    op.drop_index('idx_detection_drift_timestamp', table_name='detection_events')

    # Drop columns from detection_events
    op.drop_column('detection_events', 'original_timestamp')
    op.drop_column('detection_events', 'drift_compensated_timestamp')

    # Drop indexes from video_lifecycle_events
    op.drop_index('idx_lifecycle_unique_event', table_name='video_lifecycle_events')
    op.drop_index('idx_lifecycle_drift', table_name='video_lifecycle_events')
    op.drop_index('idx_lifecycle_video_event', table_name='video_lifecycle_events')
    op.drop_index('idx_lifecycle_session_event_created', table_name='video_lifecycle_events')

    # Drop video_lifecycle_events table
    op.drop_table('video_lifecycle_events')

    print("Video lifecycle tracking migration rolled back successfully")
