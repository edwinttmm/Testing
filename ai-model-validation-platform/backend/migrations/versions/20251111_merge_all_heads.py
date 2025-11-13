"""Merge all migration heads

Revision ID: 20251111_merge_all
Revises: 20251111_production_fields, 9a976c1f0a9a, add_completion_state, add_session_failure_tracking, add_video_timing_indexes
Create Date: 2025-11-11 12:30:00.000000

Merge migration to consolidate all parallel migration branches.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20251111_merge_all'
down_revision = (
    '20251111_production_fields',
    '9a976c1f0a9a',
    'add_completion_state',
    'add_session_failure_tracking',
    'add_video_timing_indexes'
)
branch_labels = None
depends_on = None


def upgrade():
    """
    Merge migration - no schema changes needed.
    All changes are already in the parent migrations.
    """
    pass


def downgrade():
    """
    Merge migration - no schema changes to revert.
    """
    pass
