"""add drift compensation columns to detection_events

Revision ID: 20251121_drift_compensation
Revises: f18f8e9c1590
Create Date: 2025-11-21

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251121_drift_compensation'
down_revision = '20251119_timing_quality'
branch_labels = None
depends_on = None


def upgrade():
    """Add drift compensation columns to detection_events table"""

    # Add drift_compensated_timestamp column (nullable, will be populated by service)
    op.add_column('detection_events',
        sa.Column('drift_compensated_timestamp', sa.Float(), nullable=True,
                  comment='Timestamp after applying drift compensation from video lifecycle')
    )

    # Add drift_applied boolean flag (track if drift compensation was applied)
    op.add_column('detection_events',
        sa.Column('drift_applied', sa.Boolean(), nullable=False, server_default='false',
                  comment='Flag indicating if drift compensation was applied to this detection')
    )

    # Add index for performance (often queried during GT matching)
    op.create_index(
        'ix_detection_events_drift_compensated_timestamp',
        'detection_events',
        ['drift_compensated_timestamp']
    )

    # Add composite index for session + drift queries
    op.create_index(
        'ix_detection_events_session_drift',
        'detection_events',
        ['test_session_id', 'drift_applied']
    )


def downgrade():
    """Remove drift compensation columns"""

    op.drop_index('ix_detection_events_session_drift', 'detection_events')
    op.drop_index('ix_detection_events_drift_compensated_timestamp', 'detection_events')
    op.drop_column('detection_events', 'drift_applied')
    op.drop_column('detection_events', 'drift_compensated_timestamp')
