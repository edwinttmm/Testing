"""Add timing quality tracking columns

Revision ID: 20251119_timing_quality
Revises: add_video_id_to_detection_events
Create Date: 2025-11-19

This migration adds timing quality tracking to prevent data corruption
in ground truth matching by tracking:
- Whether timing data is degraded (wall clock vs precision timing)
- Whether timing has been verified against database
- Whether detections are usable for validation

Addresses: Data corruption issues in ground truth matching when timing
quality is unknown or degraded.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251119_timing_quality'
down_revision = 'add_video_id_001'
branch_labels = None
depends_on = None


def upgrade():
    """Add timing quality tracking columns"""

    # Add timing quality columns to test_sessions table
    op.add_column('test_sessions',
        sa.Column('timing_degraded', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('test_sessions',
        sa.Column('timing_verified', sa.Boolean(), nullable=False, server_default='false'))

    # Add detection quality column to detection_events table
    op.add_column('detection_events',
        sa.Column('usable_for_validation', sa.Boolean(), nullable=False, server_default='true'))

    # Create indexes for performance on frequently queried columns
    op.create_index('idx_test_sessions_timing_degraded', 'test_sessions', ['timing_degraded'])
    op.create_index('idx_detection_events_usable', 'detection_events', ['usable_for_validation'])


def downgrade():
    """Remove timing quality tracking columns"""

    # Drop indexes first
    op.drop_index('idx_detection_events_usable', table_name='detection_events')
    op.drop_index('idx_test_sessions_timing_degraded', table_name='test_sessions')

    # Drop columns
    op.drop_column('detection_events', 'usable_for_validation')
    op.drop_column('test_sessions', 'timing_verified')
    op.drop_column('test_sessions', 'timing_degraded')
