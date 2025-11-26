"""Add usable_for_validation and timing_degraded fields to DetectionEvent

Revision ID: add_usable_validation
Revises:
Create Date: 2025-11-19

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_usable_validation'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Add usable_for_validation and timing_degraded columns to detection_events table"""
    # Add columns with default values
    op.add_column('detection_events',
        sa.Column('usable_for_validation', sa.Boolean(), nullable=False, server_default='true')
    )
    op.add_column('detection_events',
        sa.Column('timing_degraded', sa.Boolean(), nullable=False, server_default='false')
    )

    # Create indexes for performance
    op.create_index('ix_detection_events_usable_for_validation',
                    'detection_events', ['usable_for_validation'])
    op.create_index('ix_detection_events_timing_degraded',
                    'detection_events', ['timing_degraded'])


def downgrade():
    """Remove usable_for_validation and timing_degraded columns"""
    op.drop_index('ix_detection_events_timing_degraded', table_name='detection_events')
    op.drop_index('ix_detection_events_usable_for_validation', table_name='detection_events')
    op.drop_column('detection_events', 'timing_degraded')
    op.drop_column('detection_events', 'usable_for_validation')
