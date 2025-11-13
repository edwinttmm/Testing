"""Unify latency fields and mark legacy fields as deprecated

Revision ID: unify_latency_001
Revises: 0003_latency_validation_schema
Create Date: 2025-01-05 00:00:00.000000

This migration consolidates latency field handling to use actual_latency_ms
as the single source of truth. Legacy fields are maintained for backward
compatibility but marked as deprecated.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'unify_latency_001'
down_revision = '0003_latency_validation_schema'
branch_labels = None
depends_on = None


def upgrade():
    """
    Mark legacy latency fields as deprecated and backfill actual_latency_ms
    """
    # Add comments to deprecated fields (PostgreSQL only)
    # For SQLite compatibility, we wrap in try/except
    try:
        op.execute("""
            COMMENT ON COLUMN detection_events.latency_ns IS
            'DEPRECATED: Use actual_latency_ms. Kept for backward compatibility.';
        """)

        op.execute("""
            COMMENT ON COLUMN detection_events.processing_time_ms IS
            'DEPRECATED: This is processing time, not latency. Use actual_latency_ms.';
        """)

        op.execute("""
            COMMENT ON COLUMN detection_events.actual_latency_ms IS
            'CANONICAL: Actual measured latency in milliseconds from video event to hardware detection. This is the single source of truth for latency.';
        """)
    except:
        # SQLite doesn't support COMMENT, skip silently
        pass

    # Backfill actual_latency_ms for any NULL values using legacy calculation
    # Formula: video_relative_timestamp * 1000 + 50.0 (system latency)
    op.execute("""
        UPDATE detection_events
        SET actual_latency_ms = COALESCE(
            actual_latency_ms,
            (video_relative_timestamp * 1000.0) + 50.0,
            latency_threshold_ms,
            50.0
        )
        WHERE actual_latency_ms IS NULL
        AND (
            video_relative_timestamp IS NOT NULL
            OR latency_threshold_ms IS NOT NULL
        );
    """)

    # Set minimum latency to system latency (50ms) for any remaining NULL values
    op.execute("""
        UPDATE detection_events
        SET actual_latency_ms = 50.0
        WHERE actual_latency_ms IS NULL;
    """)

    # Create index on actual_latency_ms if it doesn't exist
    try:
        op.create_index(
            'ix_detection_events_actual_latency_ms',
            'detection_events',
            ['actual_latency_ms'],
            unique=False
        )
    except:
        # Index may already exist, skip
        pass


def downgrade():
    """
    Remove comments and index (optional - comments don't affect functionality)
    """
    try:
        op.execute("COMMENT ON COLUMN detection_events.latency_ns IS NULL;")
        op.execute("COMMENT ON COLUMN detection_events.processing_time_ms IS NULL;")
        op.execute("COMMENT ON COLUMN detection_events.actual_latency_ms IS NULL;")
    except:
        pass

    try:
        op.drop_index('ix_detection_events_actual_latency_ms', table_name='detection_events')
    except:
        pass
