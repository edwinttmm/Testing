"""Add sequence_elapsed_time_ms field for frontend timing data

Revision ID: seq_elapsed_001
Revises: previous_migration
Create Date: 2025-11-12

ISSUE #6 FIX: Store sequenceElapsedTime sent by frontend
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'seq_elapsed_001'
down_revision = None  # Update this with your last migration
branch_labels = None
depends_on = None


def upgrade():
    """Add sequence_elapsed_time_ms field to video_test_sequences table"""
    op.add_column('video_test_sequences',
        sa.Column('sequence_elapsed_time_ms', sa.Float(), nullable=True,
                  comment='Frontend-calculated elapsed time in sequence'))


def downgrade():
    """Remove sequence_elapsed_time_ms field"""
    op.drop_column('video_test_sequences', 'sequence_elapsed_time_ms')
