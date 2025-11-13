"""Add soft delete support to GroundTruthObject table

Revision ID: 20251031_soft_delete
Revises: 0003_latency_validation_schema
Create Date: 2025-10-31

This migration implements production-ready soft delete functionality for the GroundTruthObject table.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite
from datetime import datetime, timezone

# revision identifiers, used by Alembic.
revision = '20251031_soft_delete'
down_revision = '0003_latency_validation_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add soft delete columns and indexes to ground_truth_objects table.

    Changes:
    1. Add deleted_at (DateTime, nullable) - timestamp when soft deleted
    2. Add deleted_by (String, nullable) - user who performed deletion
    3. Add index on deleted_at for query performance
    """
    # Add soft delete columns
    with op.batch_alter_table('ground_truth_objects', schema=None) as batch_op:
        # Add deleted_at column - NULL means not deleted
        batch_op.add_column(
            sa.Column(
                'deleted_at',
                sa.DateTime(timezone=True),
                nullable=True,
                comment='Timestamp when record was soft deleted. NULL indicates active record.'
            )
        )

        # Add deleted_by column - tracks who deleted it
        batch_op.add_column(
            sa.Column(
                'deleted_by',
                sa.String(255),
                nullable=True,
                comment='User ID or identifier who performed the soft delete'
            )
        )

        # Create index on deleted_at for query performance
        # This significantly speeds up filtering by deleted_at IS NULL
        batch_op.create_index(
            'idx_gt_deleted_at',
            ['deleted_at'],
            unique=False
        )


def downgrade() -> None:
    """
    Remove soft delete columns and indexes from ground_truth_objects table.

    WARNING: This will permanently delete soft delete metadata.
    Recovery of deleted_at and deleted_by information will not be possible.
    """
    with op.batch_alter_table('ground_truth_objects', schema=None) as batch_op:
        # Drop index first
        batch_op.drop_index('idx_gt_deleted_at')

        # Drop columns
        batch_op.drop_column('deleted_by')
        batch_op.drop_column('deleted_at')
