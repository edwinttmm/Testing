"""Add session_completion_states table for idempotent retry

Revision ID: add_completion_state
Revises:
Create Date: 2025-11-11

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_completion_state'
down_revision = None  # Set to previous migration ID
branch_labels = None
depends_on = None


def upgrade():
    """Create session_completion_states table"""
    op.create_table(
        'session_completion_states',
        sa.Column('session_id', sa.String(36), nullable=False),
        sa.Column('step_completed', sa.String(), nullable=False),
        sa.Column('last_attempt', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("(datetime('now'))"), nullable=True),
        sa.PrimaryKeyConstraint('session_id')
    )

    # Create indexes for completion tracking
    op.create_index('idx_completion_state_step', 'session_completion_states', ['step_completed'])
    op.create_index('idx_completion_state_attempt', 'session_completion_states', ['last_attempt'])
    op.create_index('idx_completion_state_session_step', 'session_completion_states', ['session_id', 'step_completed'])


def downgrade():
    """Drop session_completion_states table"""
    op.drop_index('idx_completion_state_session_step', table_name='session_completion_states')
    op.drop_index('idx_completion_state_attempt', table_name='session_completion_states')
    op.drop_index('idx_completion_state_step', table_name='session_completion_states')
    op.drop_table('session_completion_states')
