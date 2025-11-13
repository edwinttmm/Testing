"""Add production fields to test_sessions

Revision ID: 20251111_production_fields
Revises: add_approval_workflow
Create Date: 2025-11-11 12:00:00.000000

This migration consolidates all production-ready fields for test_sessions:
- Failure tracking (failure_reason, failure_details, failed_at)
- Retry management (retry_count, last_retry_at)
- Approval workflow (approval_status, approved_by, approved_at, approval_comments, rejection_reason)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = '20251111_production_fields'
down_revision = 'add_approval_workflow'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add all production-ready fields to test_sessions table.

    This migration adds:
    1. Failure tracking fields for error handling
    2. Retry management for resilience
    3. Approval workflow fields (if not already present)

    Uses SQLite-compatible ALTER TABLE syntax.
    """
    # Get database connection to check existing columns
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = {col['name'] for col in inspector.get_columns('test_sessions')}

    # Failure tracking fields
    if 'failure_reason' not in existing_columns:
        op.add_column('test_sessions', sa.Column('failure_reason', sa.Text(), nullable=True))

    if 'failure_details' not in existing_columns:
        op.add_column('test_sessions', sa.Column('failure_details', sa.JSON(), nullable=True))

    if 'failed_at' not in existing_columns:
        op.add_column('test_sessions', sa.Column('failed_at', sa.DateTime(timezone=True), nullable=True))

    # Retry management fields
    if 'retry_count' not in existing_columns:
        op.add_column('test_sessions', sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'))

    if 'last_retry_at' not in existing_columns:
        op.add_column('test_sessions', sa.Column('last_retry_at', sa.DateTime(timezone=True), nullable=True))

    # Approval workflow fields (check if they exist from previous migration)
    if 'approval_status' not in existing_columns:
        op.add_column('test_sessions', sa.Column('approval_status', sa.String(20), nullable=False, server_default='pending'))

    if 'approved_by' not in existing_columns:
        op.add_column('test_sessions', sa.Column('approved_by', sa.String(255), nullable=True))

    if 'approved_at' not in existing_columns:
        op.add_column('test_sessions', sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True))

    if 'approval_comments' not in existing_columns:
        op.add_column('test_sessions', sa.Column('approval_comments', sa.Text(), nullable=True))

    if 'rejection_reason' not in existing_columns:
        op.add_column('test_sessions', sa.Column('rejection_reason', sa.Text(), nullable=True))

    # Create indexes for performance
    existing_indexes = {idx['name'] for idx in inspector.get_indexes('test_sessions')}

    # Failure tracking indexes
    if 'idx_test_sessions_failed_at' not in existing_indexes:
        op.create_index('idx_test_sessions_failed_at', 'test_sessions', ['failed_at'], unique=False)

    if 'idx_test_sessions_failure_reason' not in existing_indexes:
        op.create_index('idx_test_sessions_failure_reason', 'test_sessions', ['failure_reason'], unique=False)

    # Approval workflow indexes
    if 'idx_test_session_approval_status' not in existing_indexes:
        op.create_index('idx_test_session_approval_status', 'test_sessions', ['approval_status'], unique=False)

    if 'idx_test_session_approved_by' not in existing_indexes:
        op.create_index('idx_test_session_approved_by', 'test_sessions', ['approved_by'], unique=False)

    if 'idx_test_session_approved_at' not in existing_indexes:
        op.create_index('idx_test_session_approved_at', 'test_sessions', ['approved_at'], unique=False)

    # Composite indexes for complex queries
    if 'idx_test_session_approval_workflow' not in existing_indexes:
        op.create_index(
            'idx_test_session_approval_workflow',
            'test_sessions',
            ['approval_status', 'approved_at', 'status'],
            unique=False
        )

    if 'idx_test_session_status' not in existing_indexes:
        op.create_index('idx_test_session_status', 'test_sessions', ['status'], unique=False)


def downgrade():
    """
    Remove all production fields from test_sessions table.
    """
    # Drop indexes first
    op.drop_index('idx_test_session_status', table_name='test_sessions')
    op.drop_index('idx_test_session_approval_workflow', table_name='test_sessions')
    op.drop_index('idx_test_session_approved_at', table_name='test_sessions')
    op.drop_index('idx_test_session_approved_by', table_name='test_sessions')
    op.drop_index('idx_test_session_approval_status', table_name='test_sessions')
    op.drop_index('idx_test_sessions_failure_reason', table_name='test_sessions')
    op.drop_index('idx_test_sessions_failed_at', table_name='test_sessions')

    # Drop columns
    op.drop_column('test_sessions', 'rejection_reason')
    op.drop_column('test_sessions', 'approval_comments')
    op.drop_column('test_sessions', 'approved_at')
    op.drop_column('test_sessions', 'approved_by')
    op.drop_column('test_sessions', 'approval_status')
    op.drop_column('test_sessions', 'last_retry_at')
    op.drop_column('test_sessions', 'retry_count')
    op.drop_column('test_sessions', 'failed_at')
    op.drop_column('test_sessions', 'failure_details')
    op.drop_column('test_sessions', 'failure_reason')
