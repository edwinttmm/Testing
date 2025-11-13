"""Add session failure tracking fields

Revision ID: add_session_failure_tracking
Revises:
Create Date: 2025-11-11 12:00:00.000000

CRITICAL FIX: Adds failure tracking fields to TestSession model for
production-ready error handling and recovery.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'add_session_failure_tracking'
down_revision = None  # Update this to the latest migration
branch_labels = None
depends_on = None


def upgrade():
    """Add failure tracking columns to test_sessions table"""
    # Add failure reason column
    op.add_column('test_sessions', sa.Column('failure_reason', sa.Text(), nullable=True))
    op.create_index('ix_test_sessions_failure_reason', 'test_sessions', ['failure_reason'])

    # Add failure details JSON column
    op.add_column('test_sessions', sa.Column('failure_details', sa.JSON(), nullable=True))

    # Add failed_at timestamp
    op.add_column('test_sessions', sa.Column('failed_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_test_sessions_failed_at', 'test_sessions', ['failed_at'])

    # Add retry tracking columns
    op.add_column('test_sessions', sa.Column('retry_count', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('test_sessions', sa.Column('last_retry_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    """Remove failure tracking columns"""
    op.drop_index('ix_test_sessions_failed_at', table_name='test_sessions')
    op.drop_index('ix_test_sessions_failure_reason', table_name='test_sessions')

    op.drop_column('test_sessions', 'last_retry_at')
    op.drop_column('test_sessions', 'retry_count')
    op.drop_column('test_sessions', 'failed_at')
    op.drop_column('test_sessions', 'failure_details')
    op.drop_column('test_sessions', 'failure_reason')
