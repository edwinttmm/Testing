"""Add approval workflow to test sessions

Revision ID: add_approval_workflow
Revises: unify_latency_fields
Create Date: 2025-11-11 14:30:00.000000

This migration adds comprehensive approval workflow fields to the test_sessions table.
Enables formal approval/rejection of test results with audit trail.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_approval_workflow'
down_revision = 'unify_latency_001'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add approval workflow fields to test_sessions table.

    Fields added:
    - approval_status: Current approval state (pending/approved/rejected)
    - approved_by: User ID who approved/rejected
    - approved_at: Timestamp of approval/rejection
    - approval_comments: Optional comments from approver
    - rejection_reason: Reason for rejection if applicable
    """
    # Add approval_status column with default 'pending'
    op.add_column(
        'test_sessions',
        sa.Column('approval_status', sa.String(20), nullable=False, server_default='pending')
    )

    # Add approved_by column (nullable - only set after approval/rejection)
    op.add_column(
        'test_sessions',
        sa.Column('approved_by', sa.String(255), nullable=True)
    )

    # Add approved_at timestamp (nullable - only set after approval/rejection)
    op.add_column(
        'test_sessions',
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True)
    )

    # Add approval_comments (nullable - optional comments from approver)
    op.add_column(
        'test_sessions',
        sa.Column('approval_comments', sa.Text(), nullable=True)
    )

    # Add rejection_reason (nullable - only set if rejected)
    op.add_column(
        'test_sessions',
        sa.Column('rejection_reason', sa.Text(), nullable=True)
    )

    # Create indexes for efficient approval workflow queries
    op.create_index(
        'idx_test_session_approval_status',
        'test_sessions',
        ['approval_status'],
        unique=False
    )

    op.create_index(
        'idx_test_session_approved_by',
        'test_sessions',
        ['approved_by'],
        unique=False
    )

    op.create_index(
        'idx_test_session_approved_at',
        'test_sessions',
        ['approved_at'],
        unique=False
    )

    # Composite index for approval workflow queries
    op.create_index(
        'idx_test_session_approval_workflow',
        'test_sessions',
        ['approval_status', 'approved_at', 'status'],
        unique=False
    )


def downgrade():
    """
    Remove approval workflow fields from test_sessions table.
    """
    # Drop indexes first
    op.drop_index('idx_test_session_approval_workflow', table_name='test_sessions')
    op.drop_index('idx_test_session_approved_at', table_name='test_sessions')
    op.drop_index('idx_test_session_approved_by', table_name='test_sessions')
    op.drop_index('idx_test_session_approval_status', table_name='test_sessions')

    # Drop columns
    op.drop_column('test_sessions', 'rejection_reason')
    op.drop_column('test_sessions', 'approval_comments')
    op.drop_column('test_sessions', 'approved_at')
    op.drop_column('test_sessions', 'approved_by')
    op.drop_column('test_sessions', 'approval_status')
